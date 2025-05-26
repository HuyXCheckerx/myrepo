from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException, StaleElementReferenceException
import time
import os

# --- User-defined variables ---
LOGIN_URL = 'https://phobitcoin.com/user/login'
SELL_USDT_URL = 'https://phobitcoin.com/transaction/sellusdt'
EMAIL = 'huyxchecker@gmail.com'  # --- YOUR EMAIL ---
PASSWORD = 'Huypro159'        # --- YOUR PASSWORD ---
GENERAL_WAIT_TIME = 10  # Seconds for general element loading
POST_LOGIN_WAIT_TIME = 5 # Seconds to wait after login attempt for page to load
RETRY_WAIT_SECONDS = 0.5# Seconds to wait before retrying an action
AMOUNT_FILE_PATH = "amount.txt" # File to read the amount from

# --- Initialize WebDriver ---
driver = None

def read_amount_from_file(filepath):
    """Reads amount from the specified file."""
    try:
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            with open(filepath, 'r') as f:
                content = f.read().strip()
                print(content)
                # Attempt to convert to float to ensure it's a number, then back to string for send_keys
                return str(content)
        return None
    except (IOError, ValueError) as e:
        print(f"Error reading or parsing amount from {filepath}: {e}")
        return None

try:
    driver = webdriver.Chrome() # Ensure chromedriver is in PATH or specify executable_path
    wait = WebDriverWait(driver, GENERAL_WAIT_TIME)

    # 1. Login Process
    print(f'Navigating to login page: {LOGIN_URL}')
    driver.get(LOGIN_URL)

    print('Attempting to fill login credentials...')
    try:
        email_field = wait.until(EC.presence_of_element_located((By.NAME, 'email')))
        email_field.send_keys(EMAIL)
    except TimeoutException:
        email_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email'] | //input[contains(@placeholder, 'Email')] | //label[contains(text(),'Email')]/following-sibling::input[1]")))
        email_field.send_keys(EMAIL)
    print('Email field filled.')

    try:
        password_field = wait.until(EC.presence_of_element_located((By.NAME, 'password')))
        password_field.send_keys(PASSWORD)
    except TimeoutException:
        password_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='password'] | //input[contains(@placeholder, 'Password')] | //input[contains(@placeholder, 'Mật khẩu')] | //label[contains(text(),'Mật khẩu')]/following-sibling::input[1]")))
        password_field.send_keys(PASSWORD)
    print('Password field filled.')

    print("Waiting 8 seconds for manual CAPTCHA entry...")
    time.sleep(8) # User manually solves CAPTCHA

    print("Attempting to click login button...")
    login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(normalize-space(), 'Đăng nhập')] | //input[@type='submit'][contains(@value, 'Đăng nhập')] | //button[@type='submit']")))
    login_button.click()
    print('Clicked login button.')

    print(f"Waiting {POST_LOGIN_WAIT_TIME} seconds for login to process...")
    time.sleep(POST_LOGIN_WAIT_TIME)

    current_url = driver.current_url
    print(f"Current URL after login attempt: {current_url}")
    if "login" in current_url.lower() or "dangnhap" in current_url.lower():
        print("WARNING: Still on a login page. Login might have failed. Script will proceed but might not work.")
        # For robustness, you might want to raise an exception here or implement retries for login

    # 2. Navigate to Sell USDT Page and Process Amount
    print(f'Navigating to sell USDT page: {SELL_USDT_URL}')
    driver.get(SELL_USDT_URL)

    usdt_amount_to_send = None
    last_known_amount_from_file = None

    # Loop for inputting amount and clicking "Tiếp tục"
    tiep_tuc_clicked_successfully = False
    while not tiep_tuc_clicked_successfully:
        print("\n--- Entering Amount and Clicking 'Tiếp tục' Cycle ---")
        try:
            current_amount_from_file = read_amount_from_file(AMOUNT_FILE_PATH)
            print(current_amount_from_file)
            if current_amount_from_file is None:
                print(f"Waiting for amount in {AMOUNT_FILE_PATH}...")
                time.sleep(RETRY_WAIT_SECONDS)
                # Optional: Refresh page if file is consistently not found after some tries
                # driver.get(SELL_USDT_URL)
                continue # Retry reading the file
            if float(current_amount_from_file)< 500:
                print(f"Waiting for amount in {AMOUNT_FILE_PATH}...")
                time.sleep(RETRY_WAIT_SECONDS)
                # Optional: Refresh page if file is consistently not found after some tries
                # driver.get(SELL_USDT_URL)
                continue # Retry reading the file
            # Only update and try to input if the amount has changed or is new
            if current_amount_from_file != last_known_amount_from_file:
                usdt_amount_to_send = current_amount_from_file
                last_known_amount_from_file = current_amount_from_file
                print(f"New amount read from file: {usdt_amount_to_send}")

                print(f"Attempting to input USDT amount: {usdt_amount_to_send}...")
                usdt_amount_field = wait.until(EC.presence_of_element_located((By.ID, "btc-amount")))
                usdt_amount_field.clear()
                usdt_amount_field.send_keys(usdt_amount_to_send)
                print(f"Successfully entered '{usdt_amount_to_send}' into the USDT amount field.")
            elif usdt_amount_to_send is None: # Case where file was empty initially, then populated
                 print(f"Amount {current_amount_from_file} already known, but not yet sent. Retrying input.")
                 usdt_amount_to_send = current_amount_from_file # ensure it's set
                 # Proceed to try and input below

            if usdt_amount_to_send: # Ensure we have an amount to work with
                # Attempt to input again if it failed previously but amount is now known
                if not current_amount_from_file != last_known_amount_from_file: # if amount hasn't changed but we need to retry input
                    try:
                        usdt_amount_field = driver.find_element(By.ID, "btc-amount") # Quick check, no wait
                        if usdt_amount_field.get_attribute("value") != usdt_amount_to_send:
                             usdt_amount_field.clear()
                             usdt_amount_field.send_keys(usdt_amount_to_send)
                             print(f"Re-entered '{usdt_amount_to_send}' into the USDT amount field.")
                    except: # Element might not be there, wait.until below will handle it
                        pass


                print("Attempting to click 'Tiếp tục' button...")
                tiep_tuc_button_xpath = "//a[contains(@class, 'next-btn') and normalize-space(.)='Tiếp tục']"
                tiep_tuc_button = wait.until(EC.element_to_be_clickable((By.XPATH, tiep_tuc_button_xpath)))
                tiep_tuc_button.click()
                print("'Tiếp tục' button clicked successfully.")
                tiep_tuc_clicked_successfully = True # Exit this loop
            else:
                print(f"No valid amount available from {AMOUNT_FILE_PATH} to input yet.")
                time.sleep(RETRY_WAIT_SECONDS)


        except (TimeoutException, ElementNotInteractableException, StaleElementReferenceException) as e:
            print(f"Error during amount input or clicking 'Tiếp tục': {type(e).__name__}. Refreshing and retrying...")
            driver.get(SELL_USDT_URL) # Refresh the page
            time.sleep(RETRY_WAIT_SECONDS) # Wait a bit before retrying the loop
        except Exception as e:
            print(f"An unexpected error occurred in amount/continue cycle: {e}. Refreshing and retrying...")
            driver.get(SELL_USDT_URL)
            time.sleep(RETRY_WAIT_SECONDS)


    print("Waiting a few seconds for the page to update after 'Tiếp tục'...")
    time.sleep(3)

    # 3. Click 'Confirm' button and handle pop-up (with retries)
    confirm_and_alert_handled = False
    while not confirm_and_alert_handled:
        print("\n--- Clicking 'Confirm' and Handling Alert Cycle ---")
        try:
            print("Attempting to click 'Confirm' button...")
            # Using a more specific XPath first, then fallback if needed
            confirm_button_xpath = "//a[contains(@class, 'submit-btn') and (contains(normalize-space(),'Xác nhận') or contains(normalize-space(),'Confirm'))] | //button[contains(normalize-space(),'Xác nhận')] | //button[contains(normalize-space(),'Confirm')]"
            try:
                confirm_button = wait.until(EC.element_to_be_clickable((By.XPATH, confirm_button_xpath)))
            except TimeoutException:
                 print("Primary confirm button XPath failed, trying broader...")
                 confirm_button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[3]/div/div[2]/form/div/div[4]/a | //button[contains(normalize-space(),'Xác nhận')] | //a[contains(normalize-space(),'Confirm')] | //a[contains(normalize-space(),'Xác nhận')]")))

            confirm_button.click()
            print("'Confirm' button clicked.")

            print("Waiting for potential pop-up...")
            time.sleep(1) # Short wait for alert to potentially appear

            print('Attempting to accept alert/pop-up...')
            alert = wait.until(EC.alert_is_present()) # Will wait up to GENERAL_WAIT_TIME
            alert_text = alert.text
            print(f'Alert text: {alert_text}')
            alert.accept()
            print('Alert accepted.')
            confirm_and_alert_handled = True # Exit this loop

        except TimeoutException as e:
            # This could mean either the confirm button wasn't found, or the alert didn't appear
            current_url = driver.current_url
            if SELL_USDT_URL not in current_url and "transaction/sellusdt" not in current_url : # Check if we navigated away (e.g. to success page)
                print("Likely navigated away from sell page after confirm, assuming success or different flow.")
                confirm_and_alert_handled = True # Assume handled if not on sell page anymore
            else:
                print(f"Timeout waiting for 'Confirm' button or alert: {e}. Refreshing and retrying...")
                driver.get(SELL_USDT_URL) # Or navigate to the specific step if possible
                # Potentially, re-click "Tiếp tục" if needed to get back to confirm step
                # This part might need more sophisticated state management if refresh takes you too far back
                time.sleep(RETRY_WAIT_SECONDS)
        except (ElementNotInteractableException, StaleElementReferenceException) as e:
            print(f"Error clicking 'Confirm' button: {type(e).__name__}. Refreshing and retrying...")
            driver.get(SELL_USDT_URL)
            time.sleep(RETRY_WAIT_SECONDS)
        except Exception as e:
            print(f"An unexpected error occurred in confirm/alert cycle: {e}. Refreshing and retrying...")
            driver.get(SELL_USDT_URL)
            time.sleep(RETRY_WAIT_SECONDS)


    print('\nScript finished its main tasks. Browser will remain open for a few seconds.')
    time.sleep(10)

except Exception as e:
    print(f'\n--- An error occurred ---')
    print(str(e))
    print("The script encountered an issue. Please check the console output for details.")
    if driver:
        print("Keeping browser open for 30 seconds for review before closing...")
        time.sleep(30) # Reduced from 30000

finally:
    if driver:
        print('Closing the browser.')
        # time.sleep(30000) # This is excessively long, removing or shortening significantly
        driver.quit()
    print("Script execution ended.")