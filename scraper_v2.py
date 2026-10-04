import csv
import re
import time
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BASE_URL = "https://www.ingredientsnetwork.com/"
SUPPLIER_DIRECTORY = "https://www.ingredientsnetwork.com/company/en.html"

RAW_FILE = "companies_raw.csv"
RESULT_FILE = "results.csv"

WAIT_TIME = 10


# =========================================================
# BASIC HELPERS
# =========================================================

def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", str(text))
    return text.strip()


def normalize_url(url):
    if not url:
        return ""

    return urljoin(BASE_URL, url).split("#")[0]


def is_company_url(url):
    return bool(
        re.search(r"-comp\d+\.html", url, re.I)
    )


def is_product_url(url):
    return bool(
        re.search(r"-prod\d+\.html", url, re.I)
    )


def safe_get_text(element):
    try:
        return clean_text(element.text)
    except Exception:
        return ""


# =========================================================
# BROWSER
# =========================================================

def create_driver():

    options = Options()

    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument(
        "--disable-blink-features=AutomationControlled"
    )

    driver = webdriver.Chrome(
        options=options
    )

    driver.execute_script(
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        """
    )

    return driver


# =========================================================
# STEP 1 - OPEN WEBSITE
# =========================================================

def open_homepage(driver):

    print("\n[1] Opening Ingredients Network...")

    driver.get(BASE_URL)

    WebDriverWait(
        driver,
        WAIT_TIME
    ).until(
        EC.presence_of_element_located(
            (By.TAG_NAME, "body")
        )
    )

    time.sleep(2)

    print("[OK] Homepage loaded")


# =========================================================
# STEP 2 - CLICK SEARCH
# =========================================================

def click_search(driver):

    print("\n[2] Looking for Search button...")

    selectors = [
        "//button[normalize-space()='Search']",
        "//a[normalize-space()='Search']",
        "//*[self::button or self::a]"
        "[contains(normalize-space(.), 'Search')]",
    ]

    for selector in selectors:

        try:

            elements = driver.find_elements(
                By.XPATH,
                selector
            )

            for element in elements:

                if (
                    element.is_displayed()
                    and element.is_enabled()
                ):

                    driver.execute_script(
                        """
                        arguments[0].scrollIntoView({
                            block: 'center'
                        });
                        """,
                        element
                    )

                    time.sleep(1)

                    driver.execute_script(
                        "arguments[0].click();",
                        element
                    )

                    time.sleep(3)

                    print("[OK] Search clicked")

                    return True

        except Exception:
            continue

    print(
        "[WARNING] Search button was not found"
    )

    return False


# =========================================================
# FIND PRODUCT LINKS
# =========================================================

def collect_product_links(driver):

    product_urls = set()

    links = driver.find_elements(
        By.TAG_NAME,
        "a"
    )

    for link in links:

        try:

            href = link.get_attribute(
                "href"
            )

            if not href:
                continue

            href = normalize_url(
                href
            )

            if is_product_url(href):
                product_urls.add(href)

        except Exception:
            continue

    return sorted(product_urls)


# =========================================================
# EXTRACT SECTION
# =========================================================

def extract_section(
    driver,
    heading_text,
    end_texts=None
):
    """
    Extract text between a section heading and
    the next section.

    Uses the complete visible page text so it works
    even when the website does not use simple sibling
    elements.
    """

    if end_texts is None:
        end_texts = []

    try:

        body_text = driver.find_element(
            By.TAG_NAME,
            "body"
        ).text

        body_text = clean_text(
            body_text
        )

        if not body_text:
            return ""

        # Find requested section
        start_match = re.search(
            re.escape(heading_text),
            body_text,
            flags=re.IGNORECASE
        )

        if not start_match:
            return ""

        start_pos = start_match.end()

        remaining = body_text[
            start_pos:
        ]

        # Find first following section
        end_pos = len(remaining)

        for end_text in end_texts:

            match = re.search(
                re.escape(end_text),
                remaining,
                flags=re.IGNORECASE
            )

            if (
                match
                and match.start() < end_pos
            ):
                end_pos = match.start()

        result = remaining[
            :end_pos
        ]

        return clean_text(
            result
        )

    except Exception:

        return ""


# =========================================================
# CONTACT INFORMATION
# =========================================================

def extract_contact_information(driver):

    result = {
        "address": "",
        "email": "",
        "telephone": "",
        "website": ""
    }

    # -----------------------------------------------------
    # Expand contact information if available
    # -----------------------------------------------------

    buttons = driver.find_elements(
        By.XPATH,
        "//*[contains("
        "translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
        "'abcdefghijklmnopqrstuvwxyz'), "
        "'view all contact information')]"
    )

    for button in buttons:

        try:

            if button.is_displayed():

                driver.execute_script(
                    "arguments[0].click();",
                    button
                )

                time.sleep(1)

                break

        except Exception:
            pass

    # -----------------------------------------------------
    # EMAIL
    # -----------------------------------------------------

    try:

        links = driver.find_elements(
            By.CSS_SELECTOR,
            "a[href^='mailto:']"
        )

        for link in links:

            href = link.get_attribute(
                "href"
            )

            if href:

                result["email"] = clean_text(
                    href.replace(
                        "mailto:",
                        ""
                    )
                )

                break

    except Exception:
        pass

    # -----------------------------------------------------
    # TELEPHONE
    # -----------------------------------------------------

    try:

        links = driver.find_elements(
            By.CSS_SELECTOR,
            "a[href^='tel:']"
        )

        for link in links:

            href = link.get_attribute(
                "href"
            )

            if href:

                result["telephone"] = clean_text(
                    href.replace(
                        "tel:",
                        ""
                    )
                )

                break

    except Exception:
        pass

    # -----------------------------------------------------
    # WEBSITE
    # -----------------------------------------------------

    try:

        links = driver.find_elements(
            By.TAG_NAME,
            "a"
        )

        for link in links:

            text = clean_text(
                link.text
            ).lower()

            href = link.get_attribute(
                "href"
            )

            if (
                href
                and "website" in text
                and not href.startswith(
                    "javascript:"
                )
            ):

                result["website"] = normalize_url(
                    href
                )

                break

    except Exception:
        pass

    # -----------------------------------------------------
    # ADDRESS
    # -----------------------------------------------------

    try:

        contact_text = extract_section(
            driver,
            "Contact information",
            [
                "Upcoming events",
                "Our Top products",
                "News",
                "Content",
                "Categories"
            ]
        )

        if contact_text:

            address = contact_text

            if result["email"]:
                address = address.replace(
                    result["email"],
                    ""
                )

            if result["telephone"]:
                address = address.replace(
                    result["telephone"],
                    ""
                )

            if result["website"]:
                address = address.replace(
                    result["website"],
                    ""
                )

            address = re.sub(
                r"(?i)contact information",
                "",
                address
            )

            address = re.sub(
                r"(?i)\bemail\b",
                "",
                address
            )

            address = re.sub(
                r"(?i)\btelephone\b",
                "",
                address
            )

            address = re.sub(
                r"(?i)\bwebsite\b",
                "",
                address
            )

            result["address"] = clean_text(
                address
            )

    except Exception:
        pass

    return result


# =========================================================
# COMPANY NAME
# =========================================================

def extract_company_name(driver):

    selectors = [
        "h1",
        ".company-name",
        "[class*='company-name']"
    ]

    for selector in selectors:

        try:

            elements = driver.find_elements(
                By.CSS_SELECTOR,
                selector
            )

            for element in elements:

                text = safe_get_text(
                    element
                )

                if text:

                    return text

        except Exception:
            continue

    return ""


# =========================================================
# SCRAPE COMPANY
# =========================================================

def scrape_company(driver, url):

    print(f"  -> {url}")

    try:

        driver.get(url)

        WebDriverWait(
            driver,
            WAIT_TIME
        ).until(
            EC.presence_of_element_located(
                (By.TAG_NAME, "body")
            )
        )

        time.sleep(1)

        # =================================================
        # COMPANY NAME
        # =================================================

        company_name = extract_company_name(
            driver
        )

        # =================================================
        # COMPANY DESCRIPTION
        # =================================================

        description = extract_section(
            driver,
            "Company description",
            [
                "Quick facts",
                "Upcoming events",
                "Our Top products",
                "News",
                "Content"
            ]
        )

        # Remove company name if present
        if company_name:

            description = re.sub(
                rf"(?i)^{re.escape(company_name)}\s*",
                "",
                description
            )

        # =================================================
        # SALES MARKETS
        # =================================================

        sales_markets = extract_section(
            driver,
            "Sales markets",
            [
                "Primary business activity",
                "Affiliated categories",
                "Upcoming events"
            ]
        )

        # =================================================
        # PRIMARY BUSINESS ACTIVITY
        # =================================================

        primary_business = extract_section(
            driver,
            "Primary business activity",
            [
                "Affiliated categories",
                "Upcoming events"
            ]
        )

        # =================================================
        # CATEGORIES
        # =================================================

        categories = extract_section(
            driver,
            "Categories affiliated with",
            [
                "Upcoming events",
                "Our Top products",
                "News",
                "Content",
                "About"
            ]
        )

        # =================================================
        # EVENTS
        # =================================================

        events = extract_section(
            driver,
            "Upcoming events",
            [
                "Our Top products",
                "News",
                "Content",
                "Categories",
                "About"
            ]
        )

        # =================================================
        # CONTACT
        # =================================================

        contact = extract_contact_information(
            driver
        )

        # =================================================
        # PRODUCTS
        # =================================================

        product_urls = collect_product_links(
            driver
        )

        return {
            "company_name":
                company_name,

            "company_description":
                description,

            "sales_markets":
                sales_markets,

            "primary_business_activity":
                primary_business,

            "categories":
                categories,

            "events":
                events,

            "address":
                contact["address"],

            "email":
                contact["email"],

            "telephone":
                contact["telephone"],

            "website":
                contact["website"],

            "company_url":
                url,

            "product_urls":
                product_urls
        }

    except Exception as e:

        print(
            f"  [ERROR] {e}"
        )

        return {
            "company_name": "",
            "company_description": "",
            "sales_markets": "",
            "primary_business_activity": "",
            "categories": "",
            "events": "",
            "address": "",
            "email": "",
            "telephone": "",
            "website": "",
            "company_url": url,
            "product_urls": []
        }


# =========================================================
# GET ALL DIRECTORY PAGES
# =========================================================

def get_all_company_urls_from_directory(driver):

    print(
        "[3] Collecting ALL company URLs..."
    )

    driver.get(
        SUPPLIER_DIRECTORY
    )

    time.sleep(2)

    directory_urls = {
        SUPPLIER_DIRECTORY
    }

    # Only collect alphabet/filter directory links
    links = driver.find_elements(
        By.TAG_NAME,
        "a"
    )

    for link in links:

        try:

            text = clean_text(
                link.text
            )

            href = normalize_url(
                link.get_attribute(
                    "href"
                )
            )

            if not href:
                continue

            if is_company_url(href):
                continue

            # A-Z
            if re.fullmatch(
                r"[A-Za-z]",
                text
            ):

                if "/company/" in href:
                    directory_urls.add(
                        href
                    )

            # 0-9 / # / All
            elif re.fullmatch(
                r"(0-9|#|All)",
                text,
                re.I
            ):

                if "/company/" in href:
                    directory_urls.add(
                        href
                    )

        except Exception:
            continue

    directory_urls = sorted(
        directory_urls
    )

    print(
        f"[OK] Directory pages discovered: "
        f"{len(directory_urls)}"
    )

    all_company_urls = set()

    for i, directory_url in enumerate(
        directory_urls,
        1
    ):

        print(
            f"  Directory page "
            f"{i}/{len(directory_urls)}"
        )

        try:

            driver.get(
                directory_url
            )

            time.sleep(1)

            company_links = driver.find_elements(
                By.TAG_NAME,
                "a"
            )

            for link in company_links:

                try:

                    href = normalize_url(
                        link.get_attribute(
                            "href"
                        )
                    )

                    if (
                        href
                        and is_company_url(href)
                    ):

                        all_company_urls.add(
                            href
                        )

                except Exception:
                    continue

        except Exception as e:

            print(
                f"    [WARN] Failed: "
                f"{directory_url}"
            )

            print(
                f"           {e}"
            )

    print(
        f"[OK] Total unique companies found: "
        f"{len(all_company_urls)}"
    )

    return sorted(
        all_company_urls
    )


# =========================================================
# SAVE RAW DATA
# =========================================================

def save_raw_data(records):

    fields = [
        "company_name",
        "company_description",
        "sales_markets",
        "primary_business_activity",
        "categories",
        "events",
        "address",
        "email",
        "telephone",
        "website",
        "company_url"
    ]

    with open(
        RAW_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()

        for record in records:

            writer.writerow({
                field: record.get(
                    field,
                    ""
                )
                for field in fields
            })

    print(
        f"\n[OK] Raw data saved -> "
        f"{RAW_FILE}"
    )


# =========================================================
# CLEAN DATA
# =========================================================

def clean_record(record):

    cleaned = {}

    for key, value in record.items():

        if isinstance(
            value,
            list
        ):

            value = " | ".join(
                clean_text(item)
                for item in value
                if item
            )

        else:

            value = clean_text(
                value
            )

        value = re.sub(
            r"\s*\|\s*",
            " | ",
            value
        )

        value = re.sub(
            r"\s+",
            " ",
            value
        )

        cleaned[key] = value.strip()

    return cleaned


# =========================================================
# SAVE FINAL RESULTS
# =========================================================

def save_results(records):

    fields = [
        "Company Name",
        "Company Description",
        "Sales Markets",
        "Primary Business Activity",
        "Categories",
        "Events",
        "Address",
        "Email",
        "Telephone",
        "Website",
        "Company URL"
    ]

    with open(
        RESULT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()

        seen = set()

        for record in records:

            url = record.get(
                "company_url",
                ""
            )

            if not url:
                continue

            # Prevent duplicate companies
            if url in seen:
                continue

            seen.add(url)

            writer.writerow({
                "Company Name":
                    record.get(
                        "company_name",
                        ""
                    ),

                "Company Description":
                    record.get(
                        "company_description",
                        ""
                    ),

                "Sales Markets":
                    record.get(
                        "sales_markets",
                        ""
                    ),

                "Primary Business Activity":
                    record.get(
                        "primary_business_activity",
                        ""
                    ),

                "Categories":
                    record.get(
                        "categories",
                        ""
                    ),

                "Events":
                    record.get(
                        "events",
                        ""
                    ),

                "Address":
                    record.get(
                        "address",
                        ""
                    ),

                "Email":
                    record.get(
                        "email",
                        ""
                    ),

                "Telephone":
                    record.get(
                        "telephone",
                        ""
                    ),

                "Website":
                    record.get(
                        "website",
                        ""
                    ),

                "Company URL":
                    url
            })

    print(
        f"[OK] Final results saved -> "
        f"{RESULT_FILE}"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    driver = create_driver()

    try:

        # STEP 1
        open_homepage(
            driver
        )

        # STEP 2
        click_search(
            driver
        )

        # STEP 3
        company_urls = (
            get_all_company_urls_from_directory(
                driver
            )
        )

        print(
            f"\nTOTAL UNIQUE COMPANIES FOUND: "
            f"{len(company_urls)}"
        )

        records = []

        # =================================================
        # SCRAPE ALL COMPANIES
        # =================================================

        for index, company_url in enumerate(
            company_urls,
            start=1
        ):

            print(
                f"\n[{index}/{len(company_urls)}]"
            )

            record = scrape_company(
                driver,
                company_url
            )

            records.append(
                record
            )

        # =================================================
        # SAVE RAW DATA FIRST
        # =================================================

        save_raw_data(
            records
        )

        # =================================================
        # CLEAN DATA
        # =================================================

        cleaned_records = [
            clean_record(record)
            for record in records
        ]

        # =================================================
        # SAVE FINAL RESULTS
        # =================================================

        save_results(
            cleaned_records
        )

        print(
            "\n==================================="
        )

        print(
            "SCRAPING COMPLETED"
        )

        print(
            "==================================="
        )

    finally:

        driver.quit()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()