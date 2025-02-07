from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json

def wait_for_table_refresh(driver, wait):
    """Wait for table to refresh after page change"""
    wait.until(EC.presence_of_element_located((By.ID, 'MainContent_gvInspections')))
    time.sleep(2)  # Additional wait for content to load

def click_inspection_link(driver, row):
    """Find and click the inspection link in the 4th column (index 4)"""
    try:
        inspection_link = row.find_elements(By.TAG_NAME, 'td')[4].find_element(By.TAG_NAME, 'a')
        print(f"Clicking inspection link: {inspection_link.text}")  # Debugging
        driver.execute_script("arguments[0].click();", inspection_link)
        
        # Wait for popup content to load
        time.sleep(10)
        
    except NoSuchElementException:
        print("No inspection link found in this row.")

def get_current_page_data(driver, table):
    """Extract data from the current page, clicking each inspection link"""
    headers = [header.text.strip() for header in table.find_elements(By.TAG_NAME, 'th')]
    exclude_column = "Current Inspection Report"
    exclude_index = headers.index(exclude_column) if exclude_column in headers else None

    rows = table.find_elements(By.TAG_NAME, 'tr')[1:-2]  # Skip header and pagination rows
    page_data = []

    for row in rows:
        columns = row.find_elements(By.TAG_NAME, 'td')
        row_data = {}

        for index, column in enumerate(columns):
            if index < len(headers) and index != exclude_index:  # Exclude "Current Inspection Report"
                row_data[headers[index]] = column.text.strip()

        if any(row_data.values()):
            # Click the inspection link before moving forward
            click_inspection_link(driver, row)

            # Convert extracted row into JSON format
            formatted_record = {
                "ownerName": None,
                "tradeName": row_data.get("Name / Address", "").split("\n")[0],
                "establishmentTypes": [""],
                "mapAddress": row_data.get("Name / Address", "").split("\n")[1] if "\n" in row_data.get("Name / Address", "") else "",
                "inspections": [
                    {
                        "inspectionGrade": row_data.get("Compliance", ""),
                        "inspectionDate": row_data.get("Most Recent Inspection", ""),
                        "violationDescription": [""],  # To be extracted later
                        "violationCode": [""],  # To be extracted later
                        "inspectionDescription": [row_data.get("Inspection", "")]
                    }
                ]
            }
            page_data.append(formatted_record)
            print(f"Formatted record: {formatted_record}")  # Debugging output

    return page_data

def search_and_extract_data():
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    all_data = []

    try:
        # Navigate and perform search
        url = "https://foodsafety.kda.ks.gov/FoodSafety/Web/Inspection/PublicInspectionSearch.aspx"
        driver.get(url)
        
        search_button = wait.until(EC.presence_of_element_located(
            (By.ID, 'MainContent_btnSearch')))
        search_button.click()
        
        # Wait for initial table load
        table = wait.until(EC.presence_of_element_located(
            (By.ID, 'MainContent_gvInspections')))

        current_page = 1
        while True:
            print(f"\nProcessing page {current_page}")
            
            wait_for_table_refresh(driver, wait)
            table = driver.find_element(By.ID, 'MainContent_gvInspections')
            page_data = get_current_page_data(driver, table)
            all_data.extend(page_data)
            
            # Look for next page link
            try:
                next_page = current_page + 1
                next_page_xpath = f"//a[contains(@href, 'Page${next_page}')]"
                next_link = wait.until(EC.presence_of_element_located((By.XPATH, next_page_xpath)))
                
                first_row = table.find_element(By.CSS_SELECTOR, 'tr:nth-child(2)')
                
                driver.execute_script("arguments[0].click();", next_link)
                wait.until(EC.staleness_of(first_row))
                
                current_page = next_page
                
            except (TimeoutException, NoSuchElementException):
                print(f"No more pages found after page {current_page}")
                break

        with open('formatted_inspection_data.json', 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4, ensure_ascii=False)
        
        print(f"\nTotal records extracted: {len(all_data)}")
        print("Data saved to formatted_inspection_data.json")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    search_and_extract_data()
