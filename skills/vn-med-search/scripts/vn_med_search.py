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

class JMPHueAdapter:
    """Adapter for Tạp chí Y Dược Huế (cũ) at jmp.huemed-univ.edu.vn.

    Site PHP custom, lưu trữ các số từ 2011-2023.
    Kể từ 2023 tạp chí đổi tên và chuyển sang huejmp.vn (OJS).
    Search endpoint: GET /search.php?q=<query>
    Article URL pattern: /article.php?idbb=<slug>&Nam=<year>&id=<issue_id>
    """
    def __init__(self):
        self.name = "Tạp chí Y Dược Huế (lưu trữ 2011-2023)"
        self.base_url = "https://jmp.huemed-univ.edu.vn"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def search(self, query: str, max_results: int = 10, verbose: bool = False) -> list[Article]:
        search_url = f"{self.base_url}/search.php"
        articles = []
        try:
            log_debug(f"[{self.name}] Searching for '{query}'...", verbose)
            with httpx.Client(headers=self.headers, timeout=15.0, follow_redirects=True, verify=False) as client:
                # JMP search.php uses POST form with field 'keywords'
                response = client.post(search_url, data={"keywords": query})
                if response.status_code != 200:
                    log_debug(f"[{self.name}] Search returned status {response.status_code}", verbose)
                    return []

                soup = BeautifulSoup(response.text, "html.parser")
                links = []
                # Each article is in a div.row.d-flex.mb-2 containing h4 > a
                for row in soup.find_all("div", class_="row"):
                    h4 = row.find("h4")
                    if h4:
                        a_tag = h4.find("a", href=True)
                        if a_tag and "article.php" in a_tag.get("href", ""):
                            href = a_tag["href"]
                            url = href if href.startswith("http") else self.base_url + "/" + href.lstrip("/")
                            title = a_tag.get_text(strip=True)
                            if url not in [l[1] for l in links]:
                                links.append((title, url))

                to_fetch = links[:max_results]
                log_debug(f"[{self.name}] Found {len(links)} links. Fetching top {len(to_fetch)}...", verbose)
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    future_to_url = {executor.submit(self.fetch_details, url, title, verbose): url for title, url in to_fetch}
                    for future in concurrent.futures.as_completed(future_to_url):
                        article = future.result()
                        if article:
                            articles.append(article)
        except Exception as e:
            log_debug(f"[{self.name}] Error in search: {e}", verbose)
        return articles

    def fetch_details(self, url: str, fallback_title: str = "", verbose: bool = False) -> Article | None:
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
                    # JMP uses og:title instead of citation_title
                    og_title = soup.find("meta", property="og:title")
                    if og_title:
                        title = og_title.get("content", "")
                if not title:
                    # Fallback: first h2 is the article title on JMP
                    h2 = soup.find("h2")
                    title = h2.get_text(strip=True) if h2 else (fallback_title or "Không rõ tiêu đề")

                authors = []
                for tag in soup.find_all("meta", {"name": "citation_author"}):
                    val = tag.get("content")
                    if val and val not in authors:
                        authors.append(val)
                if not authors:
                    # JMP: authors appear as plain text in div.col-lg-9, directly after the title h2
                    col = soup.find("div", class_="col-lg-9")
                    if col:
                        lines = [t.strip() for t in col.get_text().split("\n") if t.strip()]
                        # Look for the line after the title (usually 2nd or 3rd non-empty line)
                        found_title = False
                        for line in lines:
                            if found_title and "," in line and len(line) < 300 and any(c.isalpha() for c in line):
                                # This is likely the author line
                                authors = [a.strip() for a in line.split(",") if a.strip()]
                                break
                            if title and title[:20] in line:
                                found_title = True

                abstract = None
                meta_abstract = soup.find("meta", {"name": "DC.Description"})
                if meta_abstract:
                    abstract = meta_abstract.get("content")
                if not abstract:
                    # JMP: abstract is after "Tóm tắt" h2 heading in div.col-lg-9
                    col = soup.find("div", class_="col-lg-9")
                    if col:
                        # Find mb-5 div which contains abstract text
                        mb5 = col.find("div", class_="mb-5")
                        if mb5:
                            abstract_text = mb5.get_text(strip=True)
                            if "Tóm tắt" in abstract_text:
                                abstract_text = abstract_text.replace("Tóm tắt", "").strip()
                            if abstract_text:
                                abstract = abstract_text
                meta_date = soup.find("meta", {"name": "citation_date"}) or soup.find("meta", {"name": "DC.Date.issued"})
                date_str = meta_date.get("content") if meta_date else None
                if not date_str:
                    m = re.search(r'Nam=(\d{4})', url)
                    if m:
                        date_str = m.group(1)
                year = parse_year(date_str)

                meta_doi = soup.find("meta", {"name": "citation_doi"}) or soup.find("meta", {"name": "DC.Identifier.DOI"})
                doi = meta_doi.get("content") if meta_doi else None
                if not doi:
                    doi_link = soup.find("a", href=re.compile(r'doi\.org'))
                    if doi_link:
                        doi = doi_link.get("href", "").replace("https://doi.org/", "").replace("https://dx.doi.org/", "")

                meta_pdf = soup.find("meta", {"name": "citation_pdf_url"})
                pdf_url = meta_pdf.get("content") if meta_pdf else None
                if not pdf_url:
                    pdf_link = soup.find("a", href=re.compile(r'\.pdf', re.I))
                    if pdf_link:
                        href = pdf_link.get("href", "")
                        pdf_url = href if href.startswith("http") else self.base_url + "/" + href.lstrip("/")


                log_debug(f"[{self.name}] OK: {title[:40]}", verbose)
                return Article(
                    title=title, authors=authors, abstract=abstract,
                    journal="Tạp chí Y Dược Huế (ISSN: 1859-3836)",
                    year=year, doi=doi, url=url, pdf_url=pdf_url,
                    source=self.name, language="vi"
                )
        except Exception as e:
            log_debug(f"[{self.name}] Error fetching {url}: {e}", verbose)
            return None


class MedPharmResAdapter:
    """Adapter for MedPharmRes (medpharmres.com) — English-language journal of UMP HCMC.

    MedPharmRes là phiên bản tiếng Anh của Tạp chí Y học TP.HCM,
    thuộc Đại học Y Dược TP. Hồ Chí Minh. Đã được chấp nhận vào DOAJ (2025).
    Publishes quarterly, open access, covers medicine, public health, pharmacy.
    Search endpoint: GET /archive/list_search?s_text_0=<query>&s_opt_0=all
    Article URL: /archive/view_article?doi=<doi>
    PDF URL: /download/download_pdf?pid=<pid>
    """
    def __init__(self):
        self.name = "MedPharmRes (UMP)"
        self.base_url = "https://www.medpharmres.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def search(self, query: str, max_results: int = 10, verbose: bool = False) -> list[Article]:
        search_url = f"{self.base_url}/archive/list_search"
        articles = []
        try:
            log_debug(f"[{self.name}] Searching for '{query}'...", verbose)
            with httpx.Client(headers=self.headers, timeout=15.0, follow_redirects=True, verify=False) as client:
                response = client.get(search_url, params={"s_text_0": query, "s_opt_0": "all"})
                if response.status_code != 200:
                    log_debug(f"[{self.name}] Search returned status {response.status_code}", verbose)
                    return []

                soup = BeautifulSoup(response.text, "html.parser")
                items = soup.find_all("div", class_="list_article_each")
                log_debug(f"[{self.name}] Found {len(items)} article items.", verbose)

                for item in items[:max_results]:
                    try:
                        title_tag = item.find("a", class_="list_article_title_en")
                        if not title_tag:
                            continue
                        title = title_tag.get_text(strip=True)
                        href = title_tag.get("href", "")
                        url = href if href.startswith("http") else self.base_url + href

                        # Extract DOI from href: /archive/view_article?doi=<doi>
                        doi = None
                        doi_match = re.search(r'doi=(.+?)(?:&|$)', href)
                        if doi_match:
                            doi = urllib.parse.unquote(doi_match.group(1))

                        author_div = item.find("div", class_="list_article_author_en")
                        authors_str = author_div.get_text(strip=True) if author_div else ""
                        authors = [a.strip() for a in authors_str.split(",") if a.strip()]

                        bibr_div = item.find("div", class_="list_article_bibr")
                        bibr_text = bibr_div.get_text(strip=True) if bibr_div else ""
                        year = parse_year(bibr_text)
                        if not doi:
                            doi_match2 = re.search(r'https?://doi\.org/(.+)', bibr_text)
                            if doi_match2:
                                doi = doi_match2.group(1).strip()

                        pdf_tag = item.find("a", class_="btn-warning")
                        pdf_url = None
                        if pdf_tag:
                            pdf_href = pdf_tag.get("href", "")
                            pdf_url = pdf_href if pdf_href.startswith("http") else self.base_url + pdf_href

                        articles.append(Article(
                            title=title, authors=authors, abstract=None,
                            journal="MedPharmRes", year=year, doi=doi,
                            url=url, pdf_url=pdf_url,
                            source=self.name, language="en"
                        ))
                    except Exception as e:
                        log_debug(f"[{self.name}] Error parsing item: {e}", verbose)
                        continue

        except Exception as e:
            log_debug(f"[{self.name}] Error in search: {e}", verbose)
        return articles


class TCYHTHCMAdapter:
    """Adapter for Tạp chí Y học Thành phố Hồ Chí Minh (Đại học Y Dược TP.HCM).

    Cơ chế hoạt động:
    1. Website chính (tapchiyhoctphcm.vn) dùng Google Custom Search nên không thể scrape trực tiếp.
    2. Tuy nhiên, toàn bộ bài báo được UMP cấp mã DOI thuộc prefix 10.32895 trên Crossref.
    3. Adapter truy vấn Crossref Works API với prefix 10.32895 (lọc journal tiếng Việt: Y HOC TP HO CHI MINH),
       trả về tiêu đề, tác giả, năm, DOI và link bài viết gốc trên tapchiyhoctphcm.vn.
    4. Sau đó tải song song trang chi tiết để trích xuất tóm tắt (Abstract) và link tải PDF trực tiếp.
    """
    def __init__(self):
        self.name = "Tạp chí Y học TP.HCM"
        self.prefix = "10.32895"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (VNMedSearch/1.0)"
        }

    def search(self, query: str, max_results: int = 10, verbose: bool = False) -> list[Article]:
        url = f"https://api.crossref.org/prefixes/{self.prefix}/works"
        params = {
            "query": query,
            "rows": max_results * 2,  # Dự phòng sau khi lọc tạp chí
            "sort": "relevance"
        }
        candidates = []
        try:
            log_debug(f"[{self.name}] Querying Crossref prefix {self.prefix} for '{query}'...", verbose)
            with httpx.Client(headers=self.headers, timeout=12.0) as client:
                r = client.get(url, params=params)
                if r.status_code != 200:
                    log_debug(f"[{self.name}] Crossref returned status {r.status_code}", verbose)
                    return []
                data = r.json()
                items = data.get("message", {}).get("items", [])

                for item in items:
                    container = item.get("container-title", [""])[0]
                    # Bỏ qua ấn phẩm tiếng Anh (MedPharmRes đã có adapter riêng)
                    if "MEDPHARMRES" in container.upper():
                        continue

                    title = item.get("title", [""])[0]
                    doi = item.get("DOI")
                    article_url = item.get("resource", {}).get("primary", {}).get("URL") or item.get("URL")
                    if not article_url:
                        article_url = f"https://doi.org/{doi}" if doi else ""

                    # Publication year
                    year = None
                    if "published-print" in item and "date-parts" in item["published-print"]:
                        year = item["published-print"]["date-parts"][0][0]
                    elif "published" in item and "date-parts" in item["published"]:
                        year = item["published"]["date-parts"][0][0]
                    elif "created" in item and "date-parts" in item["created"]:
                        year = item["created"]["date-parts"][0][0]

                    authors = []
                    for a in item.get("author", []):
                        full_name = f"{a.get('family', '')} {a.get('given', '')}".strip()
                        if not full_name:
                            full_name = a.get("name", "")
                        if full_name and full_name not in authors:
                            authors.append(full_name)

                    candidates.append(Article(
                        title=title,
                        authors=authors,
                        abstract=None,
                        journal="Tạp chí Y học TP. Hồ Chí Minh",
                        year=year,
                        doi=doi,
                        url=article_url,
                        pdf_url=None,
                        source=self.name,
                        language="vi"
                    ))
                    if len(candidates) >= max_results:
                        break

            log_debug(f"[{self.name}] Found {len(candidates)} candidates from Crossref. Fetching full details/PDF...", verbose)
            articles = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(self.enrich_article, c, verbose): c for c in candidates}
                for f in concurrent.futures.as_completed(futures):
                    res = f.result()
                    if res:
                        articles.append(res)
            return articles

        except Exception as e:
            log_debug(f"[{self.name}] Error searching Crossref: {e}", verbose)
            return []

    def enrich_article(self, article: Article, verbose: bool = False) -> Article:
        """Tải trang chi tiết bài báo để bóc tách Tóm tắt và link PDF trực tiếp."""
        url = article.url
        if not url or "tapchiyhoctphcm.vn" not in url:
            return article

        try:
            log_debug(f"[{self.name}] Enriching details from {url}...", verbose)
            with httpx.Client(headers=self.headers, timeout=10.0, follow_redirects=True, verify=False) as client:
                r = client.get(url)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")

                    # Link tải PDF từ thẻ meta hoặc thẻ a
                    meta_pdf = soup.find("meta", {"name": "citation_pdf_url"})
                    if meta_pdf:
                        article.pdf_url = meta_pdf.get("content")
                    if not article.pdf_url:
                        a_pdf = soup.find("a", href=re.compile(r'\.pdf', re.I))
                        if a_pdf:
                            href = a_pdf["href"]
                            article.pdf_url = href if href.startswith("http") else "https://tapchiyhoctphcm.vn" + href

                    # Tiêu đề chuẩn từ meta
                    meta_title = soup.find("meta", {"name": "citation_title"})
                    if meta_title and meta_title.get("content"):
                        article.title = meta_title.get("content")

                    # Bóc tách Tóm tắt (Abstract)
                    abstract = None
                    for h in soup.find_all(["h4", "h5", "h6"]):
                        if "tóm tắt" in h.get_text().lower():
                            p = h.find_next("p")
                            if p:
                                abstract = p.get_text(strip=True)
                                break
                    if not abstract:
                        abs_div = soup.find("div", class_=lambda x: x and "abstract" in str(x).lower())
                        if abs_div:
                            abstract = abs_div.get_text(strip=True)
                    if abstract:
                        article.abstract = abstract

        except Exception as e:
            log_debug(f"[{self.name}] Error enriching article {url}: {e}", verbose)

        return article


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
        "vista": VISTAAdapter(),
        # --- Nguồn mới tích hợp ---
        "jmp": JMPHueAdapter(),  # Tạp chí Y Dược Huế (lưu trữ cũ 2011-2023, jmp.huemed-univ.edu.vn)
        "huejmp": OJSAdapter("Tạp chí Y Dược Huế (mới)", "https://huejmp.vn/index.php/journal"),  # OJS mới từ 2023
        "tcyhtphcm": TCYHTHCMAdapter(),  # Tạp chí Y học TP.HCM (Crossref API prefix 10.32895 + tapchiyhoctphcm.vn)
        "medpharmres": MedPharmResAdapter(),  # MedPharmRes — phiên bản tiếng Anh của TPHCM (medpharmres.com)
        "vjpm": OJSAdapter("Tạp chí Y học Dự phòng", "https://vjpm.vn/index.php/vjpm"),  # Hội Y học Dự phòng VN
        "ctump": OJSAdapter("Tạp chí Y Dược học Cần Thơ", "https://tapchi.ctump.edu.vn/index.php/ctump"),  # ĐH Y Dược Cần Thơ
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
