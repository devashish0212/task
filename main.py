#!/usr/bin/env python3
"""
Food Safety Inspection Data Scraper
This script scrapes food safety inspection data from the Kansas Department of Agriculture website.
"""

import time
import json

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException
)
from selenium.webdriver.remote.webelement import WebElement


def setup_driver():
    """Initialize and configure the Chrome WebDriver."""
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    return driver


def wait_and_find_element(driver, by, value, timeout=10, retries=3):
    """
    Wait for and find an element with retry logic for stale elements.

    Args:
        driver: WebDriver instance
        by: Element locator strategy
        value: Element locator value
        timeout: Maximum wait time in seconds
        retries: Number of retry attempts

    Returns:
        WebElement if found
    """
    for attempt in range(retries):
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except StaleElementReferenceException:
            if attempt == retries - 1:
                raise
            time.sleep(1)


def get_next_page_link(driver, current_page):
    """
    Find the next page link in pagination.

    Args:
        driver: WebDriver instance
        current_page: Current page number

    Returns:
        Tuple of (next_link_element, has_next_page)
    """
    try:
        pagination_row = wait_and_find_element(
            driver,
            By.CSS_SELECTOR,
            '#MainContent_gvInspections > tbody > tr:last-child'
        )
        page_links = pagination_row.find_elements(By.TAG_NAME, 'a')
        
        for link in page_links:
            try:
                if link.text.isdigit() and int(link.text) == current_page + 1:
                    return link, True
                if link.text == "..." and 'Page$' in link.get_attribute('href'):
                    href = link.get_attribute('href')
                    if f'Page${current_page + 1}' in href:
                        return link, True
            except StaleElementReferenceException:
                continue
        
        return None, False
    except Exception as e:
        print(f"Error in get_next_page_link: {str(e)}")
        return None, False


def get_violation_details(driver, violation_link):
    """
    Extract violation details from popup window.

    Args:
        driver: WebDriver instance
        violation_link: Link element that opens violation details

    Returns:
        Dictionary containing violation details
    """
    try:
        # Open violation details popup
        driver.execute_script("arguments[0].click();", violation_link)
        print("Clicked violation link...")

        # Wait for popup to load and be visible
        popup_table = wait_and_find_element(
            driver,
            By.ID,
            'tbPublicInspectionMain',
            timeout=10
        )
        if not popup_table:
            print("Popup table not found")
            return {"error": "Popup table not found"}

        # Additional wait to ensure content is loaded
        time.sleep(3)
        
        # Get inspection date
        try:
            header_elem = wait_and_find_element(
                driver,
                By.ID,
                'MainContent_wucPublicInspectionViolations_lblHeader',
                timeout=5
            )
            inspection_date = header_elem.text.replace('Inspection Violations:', '').strip()
            print(f"Inspection date: {inspection_date}")
        except TimeoutException:
            print("Timeout waiting for header element")
            return {"error": "Header element not found"}

        # Get facility information
        try:
            facility_info = wait_and_find_element(
                driver,
                By.ID,
                'MainContent_wucPublicInspectionViolations_lblFacilityInformation',
                timeout=5
            )
            facility_text = facility_info.text.strip()
            print(f"Found facility info: {facility_text}")
        except TimeoutException:
            print("Timeout waiting for facility information")
            facility_text = None

        # Process violations
        violations = []
        index = 0
        while True:
            try:
                violation = {}
                
                # Get violation code
                code_id = f'MainContent_wucPublicInspectionViolations_rptViolations_lblRegulatorCodeType_{index}'
                code_elem = wait_and_find_element(driver, By.ID, code_id, timeout=2)
                if not code_elem:
                    break
                
                violation['code'] = code_elem.text.strip()
                print(f"Found violation code {index}: {violation['code']}")

                # Get code explanation
                try:
                    explain_id = f'MainContent_wucPublicInspectionViolations_rptViolations_lnkToggleCodeExplanation_{index}'
                    explain_link = wait_and_find_element(driver, By.ID, explain_id, timeout=2)
                    driver.execute_script("arguments[0].click();", explain_link)
                    time.sleep(0.5)
                    
                    explanation_id = f'MainContent_wucPublicInspectionViolations_rptViolations_pnlCodeExplanation_{index}'
                    explanation_div = wait_and_find_element(driver, By.ID, explanation_id, timeout=2)
                    explanation_text = explanation_div.find_element(
                        By.CSS_SELECTOR, 
                        'div > div'
                    ).text.strip()
                    violation['code_explanation'] = explanation_text
                    print(f"Found code explanation {index}")
                except Exception as e:
                    print(f"Error getting code explanation for violation {index}: {str(e)}")
                    violation['code_explanation'] = None

                # Get inspector comments
                try:
                    comments_id = f'MainContent_wucPublicInspectionViolations_rptViolations_pnlComments_{index}'
                    comments_div = wait_and_find_element(driver, By.ID, comments_id, timeout=2)
                    comments = comments_div.text.replace('Inspector Comments', '').strip()
                    violation['inspector_comments'] = comments
                    print(f"Found inspector comments {index}")
                except Exception as e:
                    print(f"Error getting inspector comments for violation {index}: {str(e)}")
                    violation['inspector_comments'] = None

                violations.append(violation)
                index += 1

            except (NoSuchElementException, TimeoutException):
                print(f"No more violations found after index {index-1}")
                break

        # Create violation record
        violation_record = {
            'inspection_date': inspection_date,
            'facility_information': facility_text,
            'violations': violations
        }
        print(inspection_date, facility_text, violations)

        # Close popup
        try:
            close_button = wait_and_find_element(driver, By.ID, 'cboxClose', timeout=5)
            if close_button:
                close_button.click()
                print("Clicked close button")
        except Exception as e:
            print(f"Error with close button: {str(e)}")

        time.sleep(2)
        return violation_record

    except Exception as e:
        print(f"Error in get_violation_details: {str(e)}")
        return {"error": str(e)}


def scrape_food_safety_data():
    """Main function to scrape and save food safety inspection data."""
    driver = setup_driver()
    results = []
    page_num = 1

    try:
        # Navigate to search page
        url = "https://foodsafety.kda.ks.gov/FoodSafety/Web/Inspection/PublicInspectionSearch.aspx"
        driver.get(url)

        # Initialize search
        search_button = wait_and_find_element(
            driver,
            By.ID,
            'MainContent_btnSearch'
        )
        search_button.click()

        # Wait for results
        wait_and_find_element(driver, By.ID, 'MainContent_gvInspections', timeout=20)

        # Get table headers
        headers = [
            header.text.strip() 
            for header in driver.find_elements(By.CSS_SELECTOR, '#MainContent_gvInspections tr th')
        ][:6]
        headers[4] = "Violations"
        print("Modified Headers:", headers)

        # Process all pages
        while True:
            print(f"Scraping page {page_num}")
            
            # Wait for table
            table = wait_and_find_element(
                driver,
                By.ID,
                'MainContent_gvInspections',
                timeout=15
            )
            time.sleep(2)

            # Process rows
            try:
                rows = table.find_elements(By.CSS_SELECTOR, 'tr')[1:-2]
                for row in rows:
                    try:
                        columns = row.find_elements(By.TAG_NAME, 'td')
                        if columns:
                            row_data = {}
                            for i, col in enumerate(columns[:6]):
                                if i < len(headers):
                                    row_data[headers[i]] = col.text.replace("\n", " ").strip()
                                    
                                    if i == 4:  # Violations column
                                        try:
                                            violation_link = col.find_element(By.TAG_NAME, 'a')
                                            violation_details = get_violation_details(driver, violation_link)
                                            row_data['violation_details'] = violation_details
                                        except NoSuchElementException:
                                            row_data['violation_details'] = None
                            
                            if any(row_data.values()):
                                results.append(row_data)
                                print(f"Added row: {row_data}")
                    except StaleElementReferenceException:
                        continue
            except StaleElementReferenceException:
                print("Table became stale, retrying...")
                continue

            # Handle pagination
            try:
                next_link, has_next = get_next_page_link(driver, page_num)
                
                if not has_next:
                    print(f"Reached last page ({page_num}). Stopping pagination.")
                    break
                
                current_first_row = wait_and_find_element(
                    driver,
                    By.CSS_SELECTOR,
                    '#MainContent_gvInspections tr:nth-child(2)'
                )
                driver.execute_script("arguments[0].click();", next_link)
                
                WebDriverWait(driver, 15).until(EC.staleness_of(current_first_row))
                page_num += 1
                
            except (NoSuchElementException, TimeoutException, StaleElementReferenceException) as e:
                print(f"Navigation error or last page reached: {str(e)}")
                break

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    
    finally:
        # Save data and cleanup
        with open("food_safety_data.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
        print(f"\nScraped {len(results)} records. Data saved to food_safety_data.json")
        driver.quit()


if __name__ == "__main__":
    scrape_food_safety_data()