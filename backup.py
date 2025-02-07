from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
import json
import time

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # REMOVE HEADLESS MODE
    driver = webdriver.Chrome(options=options)
    return driver

def wait_and_find_element(driver, by, value, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))

def get_violation_details(driver, violation_link):
    """Fetch violation details from the pop-up modal."""
    try:
        driver.execute_script("arguments[0].click();", violation_link)
        time.sleep(2)
        
        modal = wait_and_find_element(driver, By.ID, "divViolationList", timeout=10)
        violation_texts = [item.text.strip() for item in modal.find_elements(By.TAG_NAME, "li")]
        
        close_button = wait_and_find_element(driver, By.ID, "btnClose")
        close_button.click()
        return violation_texts
    except (NoSuchElementException, TimeoutException, StaleElementReferenceException):
        return None

def get_next_page_link(driver):
    """Find the <a> tag for the next page by checking pagination links."""
    try:
        pagination_section = driver.find_element(By.CSS_SELECTOR, "#MainContent_gvInspections tr:last-child")
        page_links = pagination_section.find_elements(By.TAG_NAME, "a")

        for link in page_links:
            if link.text.isdigit():
                return link
        return None
    except NoSuchElementException:
        return None

def scrape_food_safety_data():
    driver = setup_driver()
    results = []
    
    try:
        driver.get("https://foodsafety.kda.ks.gov/FoodSafety/Web/Inspection/PublicInspectionSearch.aspx")
        
        # Click Search button
        search_button = wait_and_find_element(driver, By.ID, 'MainContent_btnSearch')
        search_button.click()
        
        # Wait for table to load
        wait_and_find_element(driver, By.ID, 'MainContent_gvInspections', timeout=20)
        
        # Get column headers
        headers = [header.text.strip() for header in driver.find_elements(By.CSS_SELECTOR, '#MainContent_gvInspections tr th')][:6]
        headers[4] = "Violations"
        
        page_num = 1
        while True:
            print(f"Scraping page {page_num}...")
            table = wait_and_find_element(driver, By.ID, 'MainContent_gvInspections', timeout=15)
            time.sleep(2)
            
            row_data_list = []
            violation_links = []
            try:
                rows = table.find_elements(By.CSS_SELECTOR, 'tr')[1:-2]  # Exclude headers and footers
                for row in rows:
                    columns = row.find_elements(By.TAG_NAME, 'td')
                    if columns:
                        row_data = {headers[i]: col.text.replace("\n", " ").strip() for i, col in enumerate(columns[:6])}
                        
                        if 4 in row_data:
                            try:
                                violation_link = columns[4].find_element(By.TAG_NAME, 'a')
                                violation_links.append((row_data, violation_link))
                            except NoSuchElementException:
                                row_data['violation_details'] = None
                        
                        row_data_list.append(row_data)
            except StaleElementReferenceException:
                print("Table became stale, retrying...")
                continue
            
            # Fetch violation details
            for row_data, violation_link in violation_links:
                row_data['violation_details'] = get_violation_details(driver, violation_link)
                print(f"Updated row with violations: {row_data}")
            
            results.extend(row_data_list)
            
            # Find the next page link using <a> tags
            next_page_link = get_next_page_link(driver)
            if next_page_link is None:
                print(f"Reached last page ({page_num}). Stopping pagination.")
                break
            
            # Click the next page link
            current_first_row = wait_and_find_element(driver, By.CSS_SELECTOR, '#MainContent_gvInspections tr:nth-child(2)')
            driver.execute_script("arguments[0].click();", next_page_link)
            WebDriverWait(driver, 15).until(EC.staleness_of(current_first_row))  # Wait for page update
            page_num += 1
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        # Save to JSON
        with open("food_safety_data.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
        print(f"\nScraped {len(results)} records. Data saved to food_safety_data.json")
        driver.quit()

if __name__ == "__main__":
    scrape_food_safety_data()
