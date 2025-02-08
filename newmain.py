from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
import os

def save_data_to_json(new_entry, filename='inspection_data.json'):
    """Overwrite JSON file with new data each time program runs."""
    if not os.path.exists(filename):
        existing_data = []
    else:
        existing_data = []  # Always start fresh
    
    existing_data.append(new_entry)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, indent=4, ensure_ascii=False)
    
    print(f"Saved row to {filename}")

def wait_for_table_refresh(driver, wait):
    """Wait for table to refresh after page change"""
    print("Waiting for table to refresh...")
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="MainContent_gvInspections"]')))
    time.sleep(2)

def get_current_page_data(driver, table, wait):
    """Extract data from the current page"""
    print("Extracting headers...")
    headers = [header.text.strip() for header in table.find_elements(By.TAG_NAME, 'th')]
    print(f"Headers found: {headers}")
    exclude_column = "Current Inspection Report"
    exclude_index = headers.index(exclude_column) if exclude_column in headers else None

    print("Extracting rows...")
    rows = WebDriverWait(table, 10).until(
        EC.presence_of_all_elements_located((By.XPATH, '//*[@id="MainContent_gvInspections"]/tbody/tr'))
    )
    print(f"Total rows found: {len(rows)}")

    for i, row in enumerate(rows):
        print(f"Processing row {i+1}...")
        columns = row.find_elements(By.XPATH, './td')
        print(f"Total columns found in row {i+1}: {len(columns)}")
        if len(columns) < 5:
            print("Skipping row with insufficient columns")
            continue  

        full_trade_info = columns[0].text.strip().split("\n", 1)
        trade_name = full_trade_info[0] if full_trade_info else ""
        map_address = full_trade_info[1] if len(full_trade_info) > 1 else ""

        row_data = {
            "ownerName": None,
            "tradeName": trade_name,
            "establishmentTypes": [],
            "mapAddress": map_address,
            "inspections": [{
                "inspectionGrade": None,
                "inspectionDate": columns[1].text.strip(),
                "inspectionType": columns[2].text.strip(),
                "violationDescription": None,
                "violationCode": None,
                "inspectionDescription": None
            }]
        }

        click_inspection_link(driver, columns[4], row_data, wait)
        save_data_to_json(row_data)

def click_inspection_link(driver, column, row_data, wait):
    """Find and click the inspection link in the 4th column (index 4) only if it has text."""
    try:
        inspection_link = column.find_element(By.TAG_NAME, 'a')
        link_text = inspection_link.text.strip()

        if link_text:
            print(f"Clicking inspection link: {link_text}")
            driver.execute_script("arguments[0].click();", inspection_link)
            time.sleep(3)  # Added extra wait time for popup to load
            
            violations = []
            index = 0
            while True:
                try:
                    violation_desc_xpath = f'//*[@id="MainContent_wucPublicInspectionViolations_rptViolations_pnlCodeExplanation_{index}"]/div/div/text()'
                    violation_code_xpath = f'//*[@id="MainContent_wucPublicInspectionViolations_rptViolations_lblRegulatorCodeType_{index}"]'
                    inspection_desc_xpath = f'//*[@id="MainContent_wucPublicInspectionViolations_rptViolations_pnlComments_{index}"]'
                    
                    violation_desc_element = driver.find_element(By.XPATH, violation_desc_xpath)
                    violation_desc = violation_desc_element.get_attribute('textContent').strip() if violation_desc_element else None
                    
                    violation_code_element = driver.find_element(By.XPATH, violation_code_xpath)
                    violation_code = violation_code_element.text.strip() if violation_code_element else None
                    
                    inspection_desc_element = driver.find_element(By.XPATH, inspection_desc_xpath)
                    inspection_desc = inspection_desc_element.text.strip() if inspection_desc_element else None
                    
                    violations.append({
                        "inspectionGrade": None,
                        "inspectionDate": row_data["inspections"][0]["inspectionDate"],
                        "violationDescription": violation_desc,
                        "violationCode": violation_code,
                        "inspectionDescription": inspection_desc
                    })
                    
                    index += 1
                except NoSuchElementException:
                    break  # No more violations found
            
            if violations:
                row_data["inspections"] = violations
            
        else:
            print("No violations reported for this row.")
    except NoSuchElementException:
        print("No inspection link found in this row.")

def search_and_extract_data():
    filename = 'inspection_data.json'
    if os.path.exists(filename):
        os.remove(filename)  # Delete previous JSON file before starting new extraction

    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    try:
        url = "https://foodsafety.kda.ks.gov/FoodSafety/Web/Inspection/PublicInspectionSearch.aspx"
        driver.get(url)
        
        print("Clicking search button...")
        search_button = wait.until(EC.presence_of_element_located((By.ID, 'MainContent_btnSearch')))
        search_button.click()
        
        print("Waiting for inspection table to load...")
        table = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="MainContent_gvInspections"]')))
        
        current_page = 1
        while True:
            print(f"\nProcessing page {current_page}")
            wait_for_table_refresh(driver, wait)
            table = driver.find_element(By.XPATH, '//*[@id="MainContent_gvInspections"]')
            get_current_page_data(driver, table, wait)
            
            try:
                next_page = current_page + 1
                next_page_xpath = f"//a[contains(@href, 'Page${next_page}')']"
                next_link = wait.until(EC.presence_of_element_located((By.XPATH, next_page_xpath)))
                
                print(f"Navigating to page {next_page}...")
                first_row = table.find_element(By.CSS_SELECTOR, 'tr:nth-child(2)')
                driver.execute_script("arguments[0].click();", next_link)
                wait.until(EC.staleness_of(first_row))
                
                current_page = next_page
                
            except (TimeoutException, NoSuchElementException):
                print(f"No more pages found after page {current_page}")
                break

        print("\nData extraction completed.")

    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    search_and_extract_data()

#xpath check forvoilation description
#