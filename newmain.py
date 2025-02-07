from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
import os

def save_data_to_json(new_entry):
    """Append data to JSON file after processing each row."""
    filename = 'inspection_data.json'
    
    # Load existing data if file exists
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
                if not isinstance(existing_data, list):  # Ensure it's a list
                    existing_data = []
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []
    
    existing_data.append(new_entry)  # Append new row data

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, indent=4, ensure_ascii=False)
    
    print(f"Saved row to {filename}")


def wait_for_table_refresh(driver, wait):
    """Wait for table to refresh after page change"""
    wait.until(EC.presence_of_element_located((By.ID, 'MainContent_gvInspections')))
    time.sleep(2)  # Extra wait to ensure content loads


def get_current_page_data(driver, table, wait):
    """Extract data from the current page"""
    headers = [header.text.strip() for header in table.find_elements(By.TAG_NAME, 'th')]
    exclude_column = "Current Inspection Report"
    exclude_index = headers.index(exclude_column) if exclude_column in headers else None

    rows = table.find_elements(By.TAG_NAME, 'tr')[1:-2]  # Skip header and pagination rows
    print(len(rows))
    for i, row in enumerate(rows):
        print(f"Row {i}: {row.text.strip()}")

    for row in rows:
        columns = row.find_elements(By.TAG_NAME, 'td')

        if len(columns) < 5:  # Ensure row has enough columns
            print("Skipping row with insufficient columns")
            continue  

        # **Fix: Properly split trade name and address**
        full_trade_info = columns[0].text.strip().split("\n", 1)  # Split at the first line break
        trade_name = full_trade_info[0] if full_trade_info else ""
        map_address = full_trade_info[1] if len(full_trade_info) > 1 else ""

        row_data = {
            "ownerName": None,  # Always null
            "tradeName": trade_name,
            "establishmentTypes": [],
            "mapAddress": map_address,
            "inspections": [{
                "inspectionGrade": None,  # Always null
                "inspectionDate": columns[1].text.strip(),
                "inspectionType": columns[2].text.strip(),
                "violationDescription": None,  # Default null
                "violationCode": None,  # Default null
                "inspectionDescription": None  # Default null
            }]
        }

        # Check if there's an inspection link
        click_inspection_link(driver, columns[4], row_data, wait)

        save_data_to_json(row_data)  # Save data after each row
    
    return


def click_inspection_link(driver, column, row_data, wait):
    """Find and click the inspection link in the 4th column (index 4) only if it has text."""
    try:
        inspection_link = column.find_element(By.TAG_NAME, 'a')
        link_text = inspection_link.text.strip()

        if link_text:  # Only click if there's text like "Violation(s) X"
            print(f"Clicking inspection link: {link_text}")  # Debugging
            driver.execute_script("arguments[0].click();", inspection_link)
            time.sleep(2)  # Wait for popup content

            # TODO: Extract data from the popup (You will guide me on this)
        
        else:
            print("No violations reported for this row.")

    except NoSuchElementException:
        print("No inspection link found in this row.")


def search_and_extract_data():
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    try:
        url = "https://foodsafety.kda.ks.gov/FoodSafety/Web/Inspection/PublicInspectionSearch.aspx"
        driver.get(url)
        
        search_button = wait.until(EC.presence_of_element_located((By.ID, 'MainContent_btnSearch')))
        search_button.click()
        
        table = wait.until(EC.presence_of_element_located((By.ID, 'MainContent_gvInspections')))

        current_page = 1
        while True:
            print(f"\nProcessing page {current_page}")
            
            wait_for_table_refresh(driver, wait)
            table = driver.find_element(By.ID, 'MainContent_gvInspections')
            get_current_page_data(driver, table, wait)  # Data is now saved per row

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

        print("\nData extraction completed.")

    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        time.sleep(5)
        driver.quit()


if __name__ == "__main__":
    search_and_extract_data()
