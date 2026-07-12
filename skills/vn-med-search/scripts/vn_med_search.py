import os
import sys
import re
import httpx
from bs4 import BeautifulSoup
import urllib.parse
import json
import concurrent.futures
from dataclasses import dataclass, asdict
import typer
from rich.console import Console
from rich.table import Table

# Reconfigure stdout to use UTF-8 on Windows to avoid UnicodeEncodeErrors
sys.stdout.reconfigure(encoding='utf-8')

app = typer.Typer(help="Công cụ tìm kiếm tài liệu y khoa Việt Nam")
console = Console()

@dataclass
class Article:
    title: str
    authors: list[str]
    abstract: str | None
    journal: str | None
    year: int | None
    doi: str | None
    url: str
    pdf_url: str | None
    source: str
    language: str

def parse_year(date_str: str | None) -> int | None:
    if not date_str:
        return None
    # Look for 4 consecutive digits
    match = re.search(r'\b(19\d{2}|20\d{2})\b', date_str)
    if match:
        return int(match.group(1))
    return None

def log_debug(msg: str, verbose: bool):
    if verbose:
        print(msg, file=sys.stderr)

class OJSAdapter:
    """Adapter for OJS-based Vietnamese journals via HTML search + Metadata parsing"""
    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url  # e.g., "https://tapchinghiencuuyhoc.vn/index.php/tcncyh"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def search(self, query: str, max_results: int = 10, verbose: bool = False) -> list[Article]:
        search_url = f"{self.base_url}/search/search"
        params = {"query": query}
        articles = []
        
        try:
            log_debug(f"[{self.name}] Searching OJS for '{query}'...", verbose)
            with httpx.Client(headers=self.headers, timeout=15.0, follow_redirects=True, verify=False) as client:
                response = client.get(search_url, params=params)
                if response.status_code != 200:
                    log_debug(f"[{self.name}] Search returned status code {response.status_code}", verbose)
                    return []
                
                soup = BeautifulSoup(response.text, "html.parser")
                # Find all links pointing to article views
                links = []
                for a in soup.find_all("a"):
                    href = a.get("href", "")
                    if "/article/view/" in href:
                        # Clean up URL (remove query params)
                        clean_url = href.split("?")[0]
                        title = a.get_text(strip=True)
                        if title and clean_url not in [l[1] for l in links]:
                            links.append((title, clean_url))
                
                # Fetch details for the top N links
                # Each thread uses its own httpx.Client for thread-safety
                to_fetch = links[:max_results]
                log_debug(f"[{self.name}] Found {len(links)} article links. Fetching details for top {len(to_fetch)}...", verbose)
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    future_to_url = {executor.submit(self.fetch_details, url, verbose): url for _, url in to_fetch}
                    for future in concurrent.futures.as_completed(future_to_url):
                        article = future.result()
                        if article:
                            articles.append(article)
                            
        except Exception as e:
            log_debug(f"[{self.name}] Error in search: {e}", verbose)
            
        return articles

    def fetch_details(self, url: str, verbose: bool = False) -> Article | None:
        try:
            log_debug(f"[{self.name}] Fetching details from {url}...", verbose)
            with httpx.Client(headers=self.headers, timeout=15.0, follow_redirects=True, verify=False) as client:
                response = client.get(url)
                if response.status_code != 200:
                    log_debug(f"[{self.name}] Failed to fetch details from {url}: status {response.status_code}", verbose)
                    return None
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Extract title
                meta_title = soup.find("meta", {"name": "citation_title"}) or soup.find("meta", {"name": "DC.Title"})
                title = meta_title.get("content") if meta_title else ""
                if not title:
                    # Fallback to page title
                    title_tag = soup.find("title")
                    title = title_tag.get_text(strip=True) if title_tag else "Không rõ tiêu đề"
                    if " | " in title:
                        title = title.split(" | ")[0]
                
                # Extract authors
                authors = []
                author_tags = soup.find_all("meta", {"name": "citation_author"}) or soup.find_all("meta", {"name": "DC.Creator.PersonalName"})
                for tag in author_tags:
                    val = tag.get("content")
                    if val and val not in authors:
                        authors.append(val)
                        
                # Extract abstract (DC.Description might have multiple, e.g. vi and en)
                abstracts = []
                desc_tags = soup.find_all("meta", {"name": "DC.Description"})
                for tag in desc_tags:
                    val = tag.get("content")
                    if val and val not in abstracts:
                        abstracts.append(val)
                # Join abstracts or take the longest one (typically contains the full text abstract)
                abstract = "\n\n".join(abstracts) if abstracts else None
                
                # Extract journal name
                meta_journal = soup.find("meta", {"name": "citation_journal_title"}) or soup.find("meta", {"name": "DC.Source"})
                journal = meta_journal.get("content") if meta_journal else self.name
                
                # Extract date & year
                meta_date = soup.find("meta", {"name": "citation_date"}) or soup.find("meta", {"name": "DC.Date.issued"})
                date_str = meta_date.get("content") if meta_date else None
                year = parse_year(date_str)
                
                # Extract DOI
                meta_doi = soup.find("meta", {"name": "citation_doi"}) or soup.find("meta", {"name": "DC.Identifier.DOI"})
                doi = meta_doi.get("content") if meta_doi else None
                
                # Extract PDF URL
                meta_pdf = soup.find("meta", {"name": "citation_pdf_url"})
                pdf_url = meta_pdf.get("content") if meta_pdf else None
                if not pdf_url:
                    # Look for download link
                    pdf_tag = soup.find("a", class_="obj_galley_link pdf") or soup.find("a", class_="pdf")
                    if pdf_tag:
                        pdf_url = pdf_tag.get("href")
                
                # Language
                meta_lang = soup.find("meta", {"name": "DC.Language"})
                language = meta_lang.get("content") if meta_lang else "vi"
                
                log_debug(f"[{self.name}] Successfully fetched: {title[:30]}...", verbose)
                return Article(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    journal=journal,
                    year=year,
                    doi=doi,
                    url=url,
                    pdf_url=pdf_url,
                    source=self.name,
                    language=language
                )
        except Exception as e:
            log_debug(f"[{self.name}] Error fetching details from {url}: {e}", verbose)
            return None

class VNUAdapter:
    """Adapter for VNU Journal of Science portal (OJS3, sub-journal based).
    
    VNU hosts multiple sub-journals at https://js.vnu.edu.vn/<JOURNAL_CODE>/.
    Each sub-journal uses OJS3 which differs from OJS2 in:
    - Search URL: /<journal>/search/search (no /index.php/)
    - Result container: div.article-summary (not <a> tags directly)
    
    Currently targets the Medical & Pharmaceutical Sciences journal (MPS),
    which is most relevant for health-related queries.
    """
    def __init__(self):
        self.name = "T\u1ea1p ch\u00ed Khoa h\u1ecdc VNU - Y D\u01b0\u1ee3c"
        # OJS3 sub-journals relevant to medicine
        self.journals = [
            ("Medical and Pharmaceutical Sciences", "https://js.vnu.edu.vn/MPS"),
            ("Natural Sciences and Technology", "https://js.vnu.edu.vn/NST"),
        ]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def search(self, query: str, max_results: int = 20, verbose: bool = False) -> list[Article]:
        all_articles = []
        per_journal = max(max_results // len(self.journals), 5)
        for journal_name, base_url in self.journals:
            articles = self._search_journal(journal_name, base_url, query, per_journal, verbose)
            all_articles.extend(articles)
        return all_articles

    def _search_journal(self, journal_name: str, base_url: str, query: str, max_results: int, verbose: bool) -> list[Article]:
        search_url = f"{base_url}/search/search"
        articles = []
        try:
            log_debug(f"[{self.name}] Searching '{journal_name}' for '{query}'...", verbose)
            with httpx.Client(headers=self.headers, timeout=15.0, follow_redirects=True, verify=False) as client:
                response = client.get(search_url, params={"query": query})
                if response.status_code != 200:
                    log_debug(f"[{self.name}] '{journal_name}' search returned status {response.status_code}", verbose)
                    return []
                
                soup = BeautifulSoup(response.text, "html.parser")
                # OJS3 renders each result as div.article-summary containing a single <a>
                items = soup.find_all("div", class_="article-summary")
                log_debug(f"[{self.name}] '{journal_name}': Found {len(items)} article-summary items.", verbose)
                
                links = []
                for item in items:
                    a_tag = item.find("a", href=True)
                    if a_tag and "/article/view/" in a_tag["href"]:
                        url = a_tag["href"].split("?")[0]
                        title = a_tag.get_text(strip=True)
                        if url not in [l[1] for l in links]:
                            links.append((title, url))
                
                to_fetch = links[:max_results]
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    future_to_url = {executor.submit(self.fetch_details, url, verbose): url for _, url in to_fetch}
                    for future in concurrent.futures.as_completed(future_to_url):
                        article = future.result()
                        if article:
                            articles.append(article)
        except Exception as e:
            log_debug(f"[{self.name}] Error in search for '{journal_name}': {e}", verbose)
        return articles

    def fetch_details(self, url: str, verbose: bool = False) -> Article | None:
        """OJS3 article pages use same citation_* meta tags as OJS2."""
        try:
            log_debug(f"[{self.name}] Fetching details from {url}...", verbose)
            with httpx.Client(headers=self.headers, timeout=15.0, follow_redirects=True, verify=False) as client:
                response = client.get(url)
                if response.status_code != 200:
                    return None
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                meta_title = soup.find("meta", {"name": "citation_title"}) or soup.find("meta", {"name": "DC.Title"})
                title = meta_title.get("content") if meta_title else ""
                if not title:
                    tag = soup.find("title")
                    title = tag.get_text(strip=True).split(" | ")[0] if tag else "Kh\u00f4ng r\u00f5 ti\u00eau \u0111\u1ec1"
                
                authors = []
                for tag in soup.find_all("meta", {"name": "citation_author"}) or soup.find_all("meta", {"name": "DC.Creator.PersonalName"}):
                    val = tag.get("content")
                    if val and val not in authors:
                        authors.append(val)
                
                abstracts = []
                for tag in soup.find_all("meta", {"name": "DC.Description"}):
                    val = tag.get("content")
                    if val and val not in abstracts:
                        abstracts.append(val)
                abstract = "\n\n".join(abstracts) if abstracts else None
                
                meta_journal = soup.find("meta", {"name": "citation_journal_title"}) or soup.find("meta", {"name": "DC.Source"})
                journal = meta_journal.get("content") if meta_journal else self.name
                
                meta_date = soup.find("meta", {"name": "citation_date"}) or soup.find("meta", {"name": "DC.Date.issued"})
                date_str = meta_date.get("content") if meta_date else None
                year = parse_year(date_str)
                
                meta_doi = soup.find("meta", {"name": "citation_doi"}) or soup.find("meta", {"name": "DC.Identifier.DOI"})
                doi = meta_doi.get("content") if meta_doi else None
                
                meta_pdf = soup.find("meta", {"name": "citation_pdf_url"})
                pdf_url = meta_pdf.get("content") if meta_pdf else None
                
                meta_lang = soup.find("meta", {"name": "DC.Language"})
                language = meta_lang.get("content") if meta_lang else "en"
                
                log_debug(f"[{self.name}] OK: {title[:40]}...", verbose)
                return Article(
                    title=title, authors=authors, abstract=abstract,
                    journal=journal, year=year, doi=doi,
                    url=url, pdf_url=pdf_url,
                    source=self.name, language=language
                )
        except Exception as e:
            log_debug(f"[{self.name}] Error fetching details from {url}: {e}", verbose)
            return None

class NLVLuanAnAdapter:
    """Adapter for National Library of Vietnam Theses (Lu\u1eadn \u00e1n NLV) via HTTP scraping"""
    def __init__(self):
        self.name = "NLV Luận án"
        self.base_url = "https://luanan.nlv.gov.vn/luanan"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def search(self, query: str, max_results: int = 10, verbose: bool = False) -> list[Article]:
        params = {
            "a": "q",
            "hs": "1",
            "r": "1",
            "results": "1",
            "txf": "txIN",
            "leq": "Primary",
            "txq": query,
            "e": "-------vi-20--1--img-txIN-------"
        }
        articles = []
        
        try:
            log_debug(f"[{self.name}] Searching NLV for '{query}'...", verbose)
            with httpx.Client(headers=self.headers, timeout=20.0, follow_redirects=True, verify=False) as client:
                response = client.get(self.base_url, params=params)
                if response.status_code != 200:
                    log_debug(f"[{self.name}] Search returned status code {response.status_code}", verbose)
                    return []
                
                soup = BeautifulSoup(response.text, "html.parser")
                links = []
                for a in soup.find_all("a"):
                    href = a.get("href", "")
                    if "?a=d&" in href or "&a=d&" in href:
                        # Extract the document ID parameter 'd'
                        parsed = urllib.parse.urlparse(href)
                        qs = urllib.parse.parse_qs(parsed.query)
                        doc_ids = qs.get("d")
                        if doc_ids:
                            doc_id = doc_ids[0]
                            # Clean the document ID (remove page suffixes like .1.1)
                            clean_doc_id = doc_id.split(".")[0]
                            clean_url = f"{self.base_url}?a=d&d={clean_doc_id}"
                            if clean_url not in [l[1] for l in links]:
                                links.append((a.get_text(strip=True), clean_url))
                
                # Fetch details
                to_fetch = links[:max_results]
                log_debug(f"[{self.name}] Found {len(links)} article links. Fetching details for top {len(to_fetch)}...", verbose)
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    future_to_url = {executor.submit(self.fetch_details, url, verbose): url for _, url in to_fetch}
                    for future in concurrent.futures.as_completed(future_to_url):
                        article = future.result()
                        if article:
                            articles.append(article)
                            
        except Exception as e:
            log_debug(f"[{self.name}] Error in search: {e}", verbose)
            
        return articles

    def fetch_details(self, url: str, verbose: bool = False) -> Article | None:
        try:
            log_debug(f"[{self.name}] Fetching details from {url}...", verbose)
            with httpx.Client(headers=self.headers, timeout=20.0, follow_redirects=True, verify=False) as client:
                response = client.get(url)
                if response.status_code != 200:
                    log_debug(f"[{self.name}] Failed to fetch details from {url}: status {response.status_code}", verbose)
                    return None
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Parse metadata labels
                metadata = {}
                divs = soup.find_all("div")
                labels = ["Mã kho", "Tên luận án", "Phụ đề", "Tác giả", "Khu vực", "Nơi xuất bản", "Năm xuất bản", "Ngôn ngữ", "Từ khóa", "Tóm tắt"]
                
                for idx, div in enumerate(divs):
                    b_tag = div.find("b", recursive=False) or div.find("b")
                    if b_tag and not div.get("style", "").strip().startswith("padding-left"):
                        lbl_text = b_tag.get_text(strip=True)
                        if lbl_text in labels:
                            val = ""
                            for j in range(idx + 1, min(idx + 6, len(divs))):
                                sibling = divs[j]
                                sib_b = sibling.find("b", recursive=False)
                                if sib_b and sib_b.get_text(strip=True) in labels:
                                    break
                                val_text = sibling.get_text(strip=True)
                                if val_text:
                                    val = val_text
                                    break
                            if val:
                                metadata[lbl_text] = val
                
                title = metadata.get("Tên luận án")
                if not title:
                    title_tag = soup.find("title")
                    title = title_tag.get_text(strip=True) if title_tag else "Luận án không rõ tiêu đề"
                    if " — " in title:
                        title = title.split(" — ")[0]
                
                authors_str = metadata.get("Tác giả", "")
                authors = [a.strip() for a in authors_str.split(";") if a.strip()] if authors_str else []
                
                abstract = metadata.get("Tóm tắt")
                year_val = parse_year(metadata.get("Năm xuất bản"))
                
                log_debug(f"[{self.name}] Successfully fetched: {title[:30]}...", verbose)
                return Article(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    journal="Luận án Tiến sĩ - Thư viện Quốc gia Việt Nam",
                    year=year_val,
                    doi=None,
                    url=url,
                    pdf_url=None, # NLV views documents as images; no direct PDF download
                    source="NLV Luận án",
                    language="vi"
                )
        except Exception as e:
            log_debug(f"[{self.name}] Error fetching details from {url}: {e}", verbose)
            return None

class VISTAAdapter:
    """Adapter for VISTA STI (Công bố KH&CN Quốc gia) via HTTP POST"""
    def __init__(self):
        self.name = "VISTA STI"
        self.base_url = "https://sti.vista.gov.vn/index.php"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded"
        }

    def search(self, query: str, max_results: int = 10, verbose: bool = False) -> list[Article]:
        data = {
            "mod": "publication",
            "fun": "getlist",
            "keyword": query,
            "page": 1,
            "limit": max_results,
            "year": "",
            "area": "",
            "org": "",
            "author": "",
            "journal": "",
            "is_fulltext": 0,
            "sort": "",
            "field": "all"
        }
        articles = []
        
        try:
            log_debug(f"[{self.name}] Searching VISTA for '{query}'...", verbose)
            with httpx.Client(headers=self.headers, timeout=20.0, verify=False) as client:
                response = client.post(self.base_url, data=data)
                log_debug(f"[{self.name}] POST response status: {response.status_code}, length: {len(response.text)}", verbose)
                if response.status_code != 200 or "not found!" in response.text:
                    return []
                
                soup = BeautifulSoup(response.text, "html.parser")
                table = soup.find("table")
                if not table:
                    log_debug(f"[{self.name}] No table found in response html", verbose)
                    return []
                
                # Each data row is a publication. Skip header row.
                rows = table.find_all("tr")[1:]
                links = []
                for row in rows:
                    a_tag = row.find("a", onclick=lambda x: x and "ViewDoc" in x)
                    if a_tag:
                        onclick_val = a_tag.get("onclick", "")
                        # Extract the ID from ViewDoc('ID')
                        match = re.search(r"ViewDoc\('(\d+)'\)", onclick_val)
                        if match:
                            doc_id = match.group(1)
                            doc_url = f"https://sti.vista.gov.vn/modules/publication/expansion/ViewDoc.php?id={doc_id}"
                            links.append(doc_url)
                
                to_fetch = links[:max_results]
                log_debug(f"[{self.name}] Found {len(links)} article links. Fetching details for top {len(to_fetch)}...", verbose)
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    future_to_url = {executor.submit(self.fetch_details, url, verbose): url for url in to_fetch}
                    for future in concurrent.futures.as_completed(future_to_url):
                        article = future.result()
                        if article:
                            articles.append(article)
                            
        except Exception as e:
            log_debug(f"[{self.name}] Error in search: {e}", verbose)
            
        return articles

    def fetch_details(self, url: str, verbose: bool = False) -> Article | None:
        try:
            log_debug(f"[{self.name}] Fetching details from {url}...", verbose)
            with httpx.Client(headers=self.headers, timeout=20.0, verify=False) as client:
                response = client.get(url)
                if response.status_code != 200:
                    log_debug(f"[{self.name}] Failed to fetch details from {url}: status {response.status_code}", verbose)
                    return None
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                # The page contains details in a table structure
                metadata = {}
                for tr in soup.find_all("tr"):
                    tds = tr.find_all("td")
                    if len(tds) >= 2:
                        label = tds[0].get_text(strip=True).replace(":", "")
                        val = tds[1].get_text(strip=True)
                        metadata[label] = val
                
                title = metadata.get("Tên tài liệu") or "Không rõ tiêu đề"
                authors_str = metadata.get("Tác giả", "")
                authors = [a.strip() for a in authors_str.split(";") if a.strip()] if authors_str else []
                
                abstract = metadata.get("Tóm tắt")
                journal = metadata.get("Nguồn trích", "VISTA STI")
                
                # Extract year from Nguồn trích
                year = parse_year(journal)
                
                log_debug(f"[{self.name}] Successfully fetched: {title[:30]}...", verbose)
                return Article(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    journal=journal,
                    year=year,
                    doi=None,
                    url=url,
                    pdf_url=None, # PDFs on VISTA are usually restricted to authenticated users
                    source="VISTA STI",
                    language="vi"
                )
        except Exception as e:
            log_debug(f"[{self.name}] Error fetching details from {url}: {e}", verbose)
            return None

def parse_year_filter(year_str: str | None) -> tuple[int | None, int | None]:
    if not year_str:
        return None, None
    year_str = year_str.strip()
    if "-" in year_str:
        parts = year_str.split("-")
        try:
            start = int(parts[0].strip())
            end = int(parts[1].strip())
            return start, end
        except ValueError:
            pass
    else:
        try:
            y = int(year_str)
            return y, y
        except ValueError:
            pass
    return None, None

def filter_articles(
    articles: list[Article],
    author: str | None,
    year_filter: str | None,
    study_type: str | None,
    topic_keywords: str | None = None,
    verbose: bool = False
) -> tuple[list[Article], list[Article]]:
    filtered = []
    low_relevance = []
    
    start_year, end_year = parse_year_filter(year_filter)
    if year_filter and (start_year is None or end_year is None):
        log_debug(f"[Filter] Warning: Could not parse year filter '{year_filter}'", verbose)

    for r in articles:
        # 1. Filter by Author (case-insensitive substring)
        if author:
            author_lower = author.lower()
            if not any(author_lower in a.lower() for a in r.authors):
                log_debug(f"[Filter] Excluded (Author mismatch): {r.title[:30]}...", verbose)
                continue
                
        # 2. Filter by Year
        if year_filter and start_year is not None and end_year is not None:
            if r.year is None or not (start_year <= r.year <= end_year):
                log_debug(f"[Filter] Excluded (Year mismatch - {r.year} not in {start_year}-{end_year}): {r.title[:30]}...", verbose)
                continue
                
        # 3. Filter by Study Type
        if study_type:
            st_lower = study_type.lower()
            keywords = []
            if st_lower in ("rct", "clinical-trial"):
                keywords = ["thử nghiệm lâm sàng ngẫu nhiên", "clinical trial", "ngẫu nhiên có đối chứng", "rct", "thử nghiệm lâm sàng", "ngẫu nhiên"]
            elif st_lower in ("systematic-review", "meta-analysis", "meta"):
                keywords = ["tổng quan hệ thống", "systematic review", "meta-analysis", "tổng quan", "phân tích gộp", "phân tích hệ thống"]
            elif st_lower in ("case-report", "case"):
                keywords = ["báo cáo ca bệnh", "case report", "báo cáo lâm sàng", "ca bệnh", "báo cáo trường hợp"]
            elif st_lower == "cohort":
                keywords = ["đoàn hệ", "cohort", "nghiên cứu đoàn hệ", "theo dõi dọc"]
            elif st_lower in ("mo-ta", "descriptive", "cat-ngang"):
                keywords = ["mô tả", "cắt ngang", "cross-sectional", "descriptive", "nghiên cứu mô tả"]
            
            text_to_search = ((r.title or "") + " " + (r.abstract or "")).lower()
            if keywords and not any(kw in text_to_search for kw in keywords):
                log_debug(f"[Filter] Excluded (Study Type mismatch - keyword not found): {r.title[:30]}...", verbose)
                continue
                
        # 4. Filter by Topic Keywords (Relevance)
        if topic_keywords:
            tk_list = [kw.strip().lower() for kw in topic_keywords.split(",") if kw.strip()]
            text_to_search = ((r.title or "") + " " + (r.abstract or "")).lower()
            if tk_list and not any(kw in text_to_search for kw in tk_list):
                log_debug(f"[Filter] Marked as low relevance: {r.title[:30]}...", verbose)
                low_relevance.append(r)
                continue
                
        filtered.append(r)
        
    return filtered, low_relevance

@app.command()
def search(
    query: str,
    sources: str = typer.Option("all", help="Nguồn tìm kiếm: 'all', 'ojs', 'nlv', 'vista' hoặc danh sách phân tách bằng dấu phẩy"),
    max_results: int = typer.Option(20, help="Số lượng kết quả tối đa cho mỗi nguồn"),
    json_output: bool = typer.Option(False, "--json", help="Trả về kết quả dưới dạng JSON"),
    author: str = typer.Option(None, help="Lọc theo tên tác giả (không phân biệt hoa thường)"),
    year: str = typer.Option(None, help="Lọc theo năm xuất bản (ví dụ: 2022 hoặc 2020-2025)"),
    study_type: str = typer.Option(None, help="Lọc theo thiết kế nghiên cứu (rct, systematic-review, case-report, cohort, mo-ta)"),
    topic_keywords: str = typer.Option(None, help="Lọc độ liên quan bằng danh sách từ khóa phụ (cách nhau dấu phẩy)"),
    show_low_relevance: bool = typer.Option(False, "--show-low-relevance", help="Hiển thị cả các bài viết ít liên quan"),
    verbose: bool = typer.Option(False, "--verbose", help="Hiển thị chi tiết quá trình chạy/debug")
):
    """Tìm kiếm tài liệu y học từ các nguồn Việt Nam"""
    adapters = []
    
    # Pre-defined adapters
    all_adapters = {
        "tcncyh": OJSAdapter("Tạp chí Nghiên cứu Y học", "https://tapchinghiencuuyhoc.vn/index.php/tcncyh"),
        "vmj": OJSAdapter("Tạp chí Y học Việt Nam", "https://tapchiyhocvietnam.vn/index.php/vmj"),
        "bv108": OJSAdapter("Tạp chí Y Dược Lâm sàng 108", "https://tcydls108.benhvien108.vn/index.php/YDLS"),
        "vnu": VNUAdapter(),  # OJS3-based VNU portal; uses div.article-summary not /index.php/ pattern
        "nlv-luanan": NLVLuanAnAdapter(),
        "vista": VISTAAdapter()
    }
    
    selected_sources = [s.strip().lower() for s in sources.split(",")]
    
    if "all" in selected_sources:
        adapters = list(all_adapters.values())
    elif "ojs" in selected_sources:
        adapters = [v for k, v in all_adapters.items() if isinstance(v, OJSAdapter)]
    elif "nlv" in selected_sources:
        adapters = [all_adapters["nlv-luanan"]]
    else:
        for src in selected_sources:
            if src in all_adapters:
                adapters.append(all_adapters[src])
            else:
                log_debug(f"Cảnh báo: Không tìm thấy nguồn '{src}'", True)
                
    if not adapters:
        print("Lỗi: Không có nguồn tìm kiếm hợp lệ nào được chọn.", file=sys.stderr)
        raise typer.Exit(code=1)
        
    all_results = []
    
    if not json_output:
        console.print(f"[bold blue]Bắt đầu tìm kiếm từ khóa:[/bold blue] '{query}' trên {len(adapters)} nguồn...")
        if author or year or study_type:
            filters_desc = []
            if author: filters_desc.append(f"tác giả: '{author}'")
            if year: filters_desc.append(f"năm: '{year}'")
            if study_type: filters_desc.append(f"thiết kế: '{study_type}'")
            console.print(f"[dim]Bộ lọc áp dụng: {', '.join(filters_desc)}[/dim]")
        
    # Parallel search across adapters
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(adapters)) as executor:
        future_to_adapter = {executor.submit(adapter.search, query, max_results, verbose): adapter for adapter in adapters}
        for future in concurrent.futures.as_completed(future_to_adapter):
            adapter = future_to_adapter[future]
            try:
                results = future.result()
                all_results.extend(results)
                if not json_output:
                    console.print(f"  [green]✓[/green] {adapter.name}: Tìm thấy {len(results)} kết quả")
            except Exception as e:
                if not json_output:
                    console.print(f"  [red]✗[/red] {adapter.name}: Lỗi khi tìm kiếm - {e}")
                    
    # Deduplicate by title
    seen_titles = set()
    deduped_results = []
    for r in all_results:
        norm_title = "".join(c.lower() for c in r.title if c.isalnum())
        if norm_title not in seen_titles:
            seen_titles.add(norm_title)
            deduped_results.append(r)
            
    # Apply post-search filters
    filtered_results, low_rel_results = filter_articles(deduped_results, author, year, study_type, topic_keywords, verbose)
    
    # Sort by year (descending)
    filtered_results.sort(key=lambda x: x.year if x.year is not None else 0, reverse=True)
    low_rel_results.sort(key=lambda x: x.year if x.year is not None else 0, reverse=True)
    
    if json_output:
        # Output clean JSON
        output_data = {
            "query": query,
            "total_results": len(filtered_results),
            "total_low_relevance": len(low_rel_results) if show_low_relevance else 0,
            "filters": {
                "author": author,
                "year": year,
                "study_type": study_type,
                "topic_keywords": topic_keywords
            },
            "articles": [asdict(a) for a in filtered_results]
        }
        if show_low_relevance and low_rel_results:
            output_data["low_relevance_articles"] = [asdict(a) for a in low_rel_results]
        print(json.dumps(output_data, ensure_ascii=False, indent=2))
    else:
        console.print(f"\n[bold green]Tổng số kết quả sau khi loại trùng & lọc:[/bold green] {len(filtered_results)} bài báo/luận án có liên quan cao.\n")
        if show_low_relevance and low_rel_results:
            console.print(f"[bold yellow]Có {len(low_rel_results)} kết quả ít liên quan.[/bold yellow]\n")
        
        if not filtered_results and not (show_low_relevance and low_rel_results):
            return
            
        def print_table(results, title_prefix, title_style):
            if not results: return
            table = Table(title=f"{title_prefix} tài liệu Y học Việt Nam")
            table.add_column("STT", justify="right", style="cyan", no_wrap=True)
            table.add_column("Tiêu đề", style=title_style)
            table.add_column("Tác giả", style="green")
            table.add_column("Nguồn / Tạp chí", style="yellow")
            table.add_column("Năm", justify="center", style="blue")
            table.add_column("Đường dẫn (URL / PDF)")
            
            for idx, r in enumerate(results):
                authors_str = ", ".join(r.authors) if r.authors else "N/A"
                year_str = str(r.year) if r.year else "N/A"
                links_str = r.url
                if r.pdf_url:
                    links_str += f"\n[PDF]: {r.pdf_url}"
                    
                table.add_row(
                    str(idx + 1),
                    r.title,
                    authors_str[:50] + ("..." if len(authors_str) > 50 else ""),
                    r.journal[:40] + ("..." if len(r.journal) > 40 else "") if r.journal else r.source,
                    year_str,
                    links_str
                )
            console.print(table)
            
        print_table(filtered_results, "Kết quả tìm kiếm", "magenta")
        if show_low_relevance:
            print_table(low_rel_results, "Kết quả ít liên quan", "dim")

if __name__ == "__main__":
    app()
