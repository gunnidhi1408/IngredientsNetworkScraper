import csv
import re
import time
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ============================================================
# SETTINGS
# ============================================================

BASE_URL = "https://www.ingredientsnetwork.com/"
SUPPLIER_DIRECTORY = "https://www.ingredientsnetwork.com/company/en.html"

COMPANY_FILE = "companies.csv"
PRODUCT_FILE = "products.csv"

WAIT_TIME = 5


# ============================================================
# BROWSER
# ============================================================

def create_driver():

    options = Options()

    # Browser stays visible
    # options.add_argument("--headless")

    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-notifications")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)

    return driver


# ============================================================
# TEXT / URL HELPERS
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_url(url):

    if not url:
        return ""

    return urljoin(BASE_URL, url).split("#")[0]


def get_company_id(url):

    if not url:
        return None

    match = re.search(
        r"-comp(\d+)\.html",
        url,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return None


def is_company_url(url):

    if not url:
        return False

    return bool(
        re.search(
            r"-comp\d+\.html",
            url,
            re.IGNORECASE
        )
    )


def is_product_url(url):

    if not url:
        return False

    return bool(
        re.search(
            r"-prod\d+\.html",
            url,
            re.IGNORECASE
        )
    )


# ============================================================
# GET COMPANIES
# ============================================================

def scrape_companies(driver):

    companies = {}

    print()
    print("=" * 70)
    print("OPENING SUPPLIER DIRECTORY")
    print("=" * 70)

    print(SUPPLIER_DIRECTORY)

    driver.get(SUPPLIER_DIRECTORY)

    time.sleep(3)

    # --------------------------------------------------------
    # The directory contains alphabet links.
    # Open every letter page and collect company URLs.
    # --------------------------------------------------------

    directory_links = driver.find_elements(
        By.TAG_NAME,
        "a"
    )

    directory_pages = set()

    for link in directory_links:

        href = link.get_attribute("href")

        if not href:
            continue

        href = normalize_url(href)

        text = clean_text(link.text).upper()

        # Alphabet directory links
        if re.fullmatch(
            r"[A-Z0-9](?:-[A-Z0-9])?",
            text
        ):
            directory_pages.add(href)

    # --------------------------------------------------------
    # Always include the main directory itself
    # --------------------------------------------------------

    directory_pages.add(SUPPLIER_DIRECTORY)

    print(
        "Directory pages found:",
        len(directory_pages)
    )

    # --------------------------------------------------------
    # Open each directory page
    # --------------------------------------------------------

    for page_number, directory_page in enumerate(
        sorted(directory_pages),
        start=1
    ):

        print()
        print(
            f"[DIRECTORY {page_number}/{len(directory_pages)}]"
        )

        print(directory_page)

        try:

            driver.get(directory_page)

            time.sleep(2)

            # Scroll a little to trigger dynamic content
            for _ in range(2):

                driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )

                time.sleep(0.5)

            links = driver.find_elements(
                By.TAG_NAME,
                "a"
            )

            page_companies = 0

            for link in links:

                href = link.get_attribute("href")

                if not href:
                    continue

                href = normalize_url(href)

                if not is_company_url(href):
                    continue

                try:
                    name = clean_text(link.text)
                except:
                    name = ""

                # Sometimes link text is empty.
                # Try aria-label/title.
                if not name:

                    try:
                        name = clean_text(
                            link.get_attribute("title")
                        )
                    except:
                        name = ""

                if not name:

                    try:
                        name = clean_text(
                            link.get_attribute("aria-label")
                        )
                    except:
                        name = ""

                if href not in companies:

                    companies[href] = {
                        "company_name": name,
                        "url": href
                    }

                    page_companies += 1

            print(
                "New companies found:",
                page_companies
            )

        except Exception as e:

            print(
                "Directory error:",
                e
            )

    # --------------------------------------------------------
    # If alphabet links were not detected correctly,
    # inspect the main directory again.
    # --------------------------------------------------------

    if len(companies) == 0:

        print()
        print(
            "Alphabet pages were not detected."
        )

        print(
            "Trying direct company links from directory..."
        )

        try:

            driver.get(SUPPLIER_DIRECTORY)

            time.sleep(3)

            links = driver.find_elements(
                By.TAG_NAME,
                "a"
            )

            for link in links:

                href = link.get_attribute("href")

                if not href:
                    continue

                href = normalize_url(href)

                if not is_company_url(href):
                    continue

                name = clean_text(
                    link.text
                )

                if not name:

                    name = clean_text(
                        link.get_attribute("title")
                    )

                if href not in companies:

                    companies[href] = {
                        "company_name": name,
                        "url": href
                    }

        except Exception as e:

            print(
                "Fallback company discovery error:",
                e
            )

    # --------------------------------------------------------
    # Remove entries with completely empty names
    # --------------------------------------------------------

    cleaned_companies = []

    for url, company in companies.items():

        name = company["company_name"]

        if not name:

            # Extract readable name from URL
            name = re.sub(
                r"-comp\d+\.html$",
                "",
                url,
                flags=re.IGNORECASE
            )

            name = name.replace(
                "https://www.ingredientsnetwork.com/",
                ""
            )

            name = name.replace(
                "-",
                " "
            )

            name = clean_text(name).title()

            company["company_name"] = name

        cleaned_companies.append(company)

    return cleaned_companies


# ============================================================
# FIND TOP PRODUCTS ON COMPANY PAGE
# ============================================================

def get_top_product_links(driver):

    product_urls = set()

    links = driver.find_elements(
        By.TAG_NAME,
        "a"
    )

    for link in links:

        href = link.get_attribute("href")

        if not href:
            continue

        href = normalize_url(href)

        if is_product_url(href):

            product_urls.add(href)

    return product_urls


# ============================================================
# FIND "VIEW ALL OUR PRODUCTS"
# ============================================================

def get_all_products_url(
    driver,
    company_url
):

    links = driver.find_elements(
        By.TAG_NAME,
        "a"
    )

    for link in links:

        try:
            text = clean_text(
                link.text
            ).upper()
        except:
            text = ""

        href = link.get_attribute("href")

        if not href:
            continue

        href = normalize_url(href)

        if "VIEW ALL OUR PRODUCTS" in text:

            return href

    # --------------------------------------------------------
    # FALLBACK USING COMPANY ID
    # --------------------------------------------------------

    company_id = get_company_id(
        company_url
    )

    if company_id:

        return (
            "https://www.ingredientsnetwork.com/live/search/"
            f"searchresults46v2.jsp?"
            f"companyid={company_id}"
            f"&searchtype=products"
        )

    return None


# ============================================================
# SCRAPE ALL PRODUCTS PAGE
# ============================================================

def scrape_product_search_page(
    driver,
    product_search_url
):

    product_urls = set()

    print()
    print("Opening ALL PRODUCTS page:")
    print(product_search_url)

    try:

        driver.get(product_search_url)

        time.sleep(3)

        # ----------------------------------------------------
        # Scroll several times
        # ----------------------------------------------------

        previous_height = 0

        for _ in range(6):

            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )

            time.sleep(1)

            current_height = driver.execute_script(
                "return document.body.scrollHeight"
            )

            if current_height == previous_height:
                break

            previous_height = current_height

        # ----------------------------------------------------
        # Collect product links
        # ----------------------------------------------------

        links = driver.find_elements(
            By.TAG_NAME,
            "a"
        )

        for link in links:

            href = link.get_attribute(
                "href"
            )

            if not href:
                continue

            href = normalize_url(href)

            if is_product_url(href):

                product_urls.add(href)

    except Exception as e:

        print(
            "Product search error:",
            e
        )

    print(
        "Products found:",
        len(product_urls)
    )

    return product_urls


# ============================================================
# SCRAPE COMPANY
# ============================================================

def scrape_company(
    driver,
    company
):

    company_name = company["company_name"]
    company_url = company["url"]

    print()
    print("=" * 70)
    print("COMPANY:", company_name)
    print("URL:", company_url)
    print("=" * 70)

    product_urls = set()

    try:

        driver.get(company_url)

        time.sleep(2)

        # ----------------------------------------------------
        # TOP PRODUCTS
        # ----------------------------------------------------

        top_products = get_top_product_links(
            driver
        )

        print(
            "Visible/top products:",
            len(top_products)
        )

        product_urls.update(
            top_products
        )

        # ----------------------------------------------------
        # ALL PRODUCTS URL
        # ----------------------------------------------------

        all_products_url = get_all_products_url(
            driver,
            company_url
        )

        if all_products_url:

            print(
                "All products URL:",
                all_products_url
            )

            full_products = scrape_product_search_page(
                driver,
                all_products_url
            )

            product_urls.update(
                full_products
            )

        else:

            print(
                "No all-products URL found."
            )

    except Exception as e:

        print(
            "Company error:",
            e
        )

    print(
        "TOTAL UNIQUE PRODUCTS:",
        len(product_urls)
    )

    return product_urls


# ============================================================
# SCRAPE PRODUCT PAGE
# ============================================================

def scrape_product_page(
    driver,
    product_url,
    company_name=""
):

    data = {
        "product_name": "",
        "company": company_name,
        "description": "",
        "url": product_url
    }

    try:

        driver.get(product_url)

        time.sleep(1.5)

        # ----------------------------------------------------
        # PRODUCT NAME
        # ----------------------------------------------------

        product_name = ""

        try:

            h1 = WebDriverWait(
                driver,
                WAIT_TIME
            ).until(
                EC.presence_of_element_located(
                    (By.TAG_NAME, "h1")
                )
            )

            product_name = clean_text(
                h1.text
            )

        except:
            pass

        # ----------------------------------------------------
        # FALLBACK TITLE
        # ----------------------------------------------------

        if not product_name:

            try:

                product_name = clean_text(
                    driver.title
                )

                product_name = re.sub(
                    r"\s*\|\s*Ingredients Network.*$",
                    "",
                    product_name,
                    flags=re.IGNORECASE
                )

            except:
                pass

        data["product_name"] = product_name

        # ----------------------------------------------------
        # BODY
        # ----------------------------------------------------

        try:

            body = driver.find_element(
                By.TAG_NAME,
                "body"
            )

            body_text = clean_text(
                body.text
            )

        except:

            body_text = ""

        # ----------------------------------------------------
        # COMPANY
        # ----------------------------------------------------

        company_patterns = [

            r"Company\s*[:\-]\s*(.+?)(?:\s+Product|\s+Description|$)",

            r"Manufacturer\s*[:\-]\s*(.+?)(?:\s+Product|\s+Description|$)"

        ]

        for pattern in company_patterns:

            match = re.search(
                pattern,
                body_text,
                re.IGNORECASE
            )

            if match:

                detected_company = clean_text(
                    match.group(1)
                )

                if detected_company:

                    data["company"] = (
                        detected_company
                    )

                break

        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        description = ""

        selectors = [

            ".product-description",

            ".description",

            "[class*='description']",

            "[id*='description']"

        ]

        for selector in selectors:

            try:

                elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    selector
                )

                for element in elements:

                    text = clean_text(
                        element.text
                    )

                    if len(text) > len(
                        description
                    ):

                        description = text

            except:
                pass

        # ----------------------------------------------------
        # BODY FALLBACK
        # ----------------------------------------------------

        if not description and body_text:

            patterns = [

                r"Description\s*(.*?)(?:Uses|Applications|Specifications|Contact|Read more|$)",

                r"Product Description\s*(.*?)(?:Uses|Applications|Specifications|Contact|Read more|$)"

            ]

            for pattern in patterns:

                match = re.search(
                    pattern,
                    body_text,
                    re.IGNORECASE
                )

                if match:

                    description = clean_text(
                        match.group(1)
                    )

                    if description:
                        break

        data["description"] = description

    except Exception as e:

        print(
            "Product error:",
            product_url,
            "|",
            e
        )

    return data


# ============================================================
# SAVE COMPANIES
# ============================================================

def save_companies(
    companies
):

    with open(
        COMPANY_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "company_name",
                "url"
            ]
        )

        writer.writeheader()

        for company in companies:

            writer.writerow(
                company
            )

    print()
    print(
        "Companies saved:",
        COMPANY_FILE
    )


# ============================================================
# SAVE PRODUCTS
# ============================================================

def save_products(
    products
):

    with open(
        PRODUCT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "product_name",
                "company",
                "description",
                "url"
            ]
        )

        writer.writeheader()

        for product in products:

            writer.writerow(
                product
            )

    print()
    print(
        "Products saved:",
        PRODUCT_FILE
    )


# ============================================================
# MAIN
# ============================================================

def main():

    driver = create_driver()

    try:

        # ====================================================
        # STEP 1: COMPANIES
        # ====================================================

        companies = scrape_companies(
            driver
        )

        print()
        print("=" * 70)
        print(
            "TOTAL COMPANIES FOUND:",
            len(companies)
        )
        print("=" * 70)

        save_companies(
            companies
        )

        if len(companies) == 0:

            print()
            print(
                "ERROR: No companies were found."
            )

            print(
                "Check the supplier directory manually:"
            )

            print(
                SUPPLIER_DIRECTORY
            )

            input(
                "Press ENTER to close browser..."
            )

            return

        # ====================================================
        # STEP 2: PRODUCTS
        # ====================================================

        all_product_urls = {}

        for company_index, company in enumerate(
            companies,
            start=1
        ):

            print()
            print(
                f"[COMPANY {company_index}/{len(companies)}]"
            )

            print(
                company["company_name"]
            )

            product_urls = scrape_company(
                driver,
                company
            )

            for product_url in product_urls:

                if product_url not in all_product_urls:

                    all_product_urls[
                        product_url
                    ] = company[
                        "company_name"
                    ]

        # ====================================================
        # PRODUCT URL TOTAL
        # ====================================================

        print()
        print("=" * 70)

        print(
            "TOTAL UNIQUE PRODUCT URLS:",
            len(all_product_urls)
        )

        print("=" * 70)

        # ====================================================
        # STEP 3: PRODUCT DETAILS
        # ====================================================

        products = []

        total_products = len(
            all_product_urls
        )

        for index, item in enumerate(
            all_product_urls.items(),
            start=1
        ):

            product_url = item[0]
            company_name = item[1]

            print()
            print(
                f"[PRODUCT {index}/{total_products}]"
            )

            print(
                "Company:",
                company_name
            )

            print(
                "URL:",
                product_url
            )

            product = scrape_product_page(
                driver,
                product_url,
                company_name
            )

            products.append(
                product
            )

            print(
                "Product:",
                product["product_name"]
            )

        # ====================================================
        # STEP 4: SAVE
        # ====================================================

        save_products(
            products
        )

        # ====================================================
        # FINAL
        # ====================================================

        print()
        print("=" * 70)
        print("SCRAPING COMPLETE")
        print("=" * 70)

        print(
            "TOTAL COMPANIES:",
            len(companies)
        )

        print(
            "TOTAL PRODUCTS:",
            len(products)
        )

        print()
        print(
            "Companies CSV:",
            COMPANY_FILE
        )

        print(
            "Products CSV:",
            PRODUCT_FILE
        )

        print()
        print(
            "Press ENTER to close browser..."
        )

        input()

    finally:

        driver.quit()

        print()
        print(
            "Browser closed."
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()