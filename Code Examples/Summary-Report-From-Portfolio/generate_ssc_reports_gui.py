# Get Summary Reports for all companies in a Portfolio
import json
import requests

import time

import zipfile
import os

import datetime

import tkinter as tk
from tkinter import ttk
from tkinter import *

# Global Variables
api_token = ""
portfolio_id = ""
report_format = ""
branding = "securityscorecard"
file_name = "downloaded-reports"
language = "default"

text_area = None # for GUI writing

def main(api_token_input, portfolio_id_input, file_format_input, branding_input, file_name_input, language_input):

    global api_token
    global portfolio_id
    global report_format
    global branding
    global file_name
    global language

    api_token = api_token_input
    portfolio_id = portfolio_id_input
    report_format = file_format_input
    branding = branding_input
    file_name = file_name_input
    language = language_input

    # Get all companies in a Portfolio
    portfolio_companies = get_portfolio_companies(portfolio_id)

    # Generate summary reports for each company in the Portfolio. (Can specify branding choice here)
    report_confirmations = generate_summary_reports(portfolio_companies, branding)

    # Check to see if reports are completed
    completed_reports = wait_for_completed_reports(report_confirmations)

    # Download all PDFs to a ZIP file
    download_and_zip_reports(completed_reports, report_format, file_name, language)


def get_portfolio_companies(portfolio_id):
    """
    Retrieves companies within a portfolio from the SecurityScorecard API.

    Args:
        portfolio_id (str): The ID of the portfolio.

    Returns:
        dict or None: A dictionary containing the API response (JSON), or None if an error occurs.
        Prints an error message to standard error if there's a problem with the API call.
    """
    url = f"https://api.securityscorecard.io/portfolios/{portfolio_id}/companies"
    headers = {
        "Authorization": f"Token {api_token}",
        "accept": "application/json; charset=utf-8",
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        # Response successful:
        response_dict = response.json()["entries"]  # Parse the JSON response
        print_to_program(f"Successfully retrieved Portfolio ID: {portfolio_id}")
        print_to_program(f"{len(response_dict)} Companies Retrieved in Portfolio.")
        return response_dict
    except requests.exceptions.RequestException as e:
        print_to_program(f"Error fetching portfolio companies: {e}")
        if response is not None:
            try:
                print_to_program(f"Response Body: {response.json()}") # Attempt to print the response body, even if an error occurred.
            except json.JSONDecodeError:
                print_to_program(f"Response Text: {response.text}") # If the response isn't valid JSON, print the raw text.
        return None
    except json.JSONDecodeError as e:
        print_to_program(f"Error decoding JSON response: {e}")
        if response is not None:
            print_to_program(f"Response Text: {response.text}") # Print raw text if json decode fails.
        return None

def generate_summary_reports(portfolio_companies, branding):
    """
    Generates summary reports for a list of scorecard identifiers.

    Args:
        portfolio_companies (list): A list of scorecard identifiers.
        branding (str): The branding to use for the reports.

    Returns:
        dict: A dictionary where keys are scorecard identifiers and values are the API responses (dicts) or None if an error occurred for that identifier.
    """

    url = "https://api.securityscorecard.io/reports/summary"
    headers = {
        "Authorization": f"Token {api_token}",
        "accept": "application/json; charset=utf-8",
        "content-type": "application/json",
    }

    results = {}
    for company in portfolio_companies:
        company_domain = company["domain"]
        payload = {
            "scorecard_identifier": company_domain,
            "branding": branding
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            results[company_domain] = response.json()
            print_to_program(f"Successfully requested report generation for: {company_domain}")

        except requests.exceptions.RequestException as e:
            print_to_program(f"Error generating report for {company_domain}: {e}")
            results[company_domain] = None
            if response is not None:
                try:
                    print_to_program(f"Response Body: {response.json()}")
                except json.JSONDecodeError:
                    print_to_program(f"Response Text: {response.text}")
        except json.JSONDecodeError as e:
            print_to_program(f"Error decoding JSON response for {company_domain}: {e}")
            results[company_domain] = None
            if response is not None:
                print_to_program(f"Response Text: {response.text}")
    
    print_to_program(f"{len(results)} Reports successfully requested for generation.")
    return results

def wait_for_completed_reports(report_confirmations):
    """
    Calls the SecurityScorecard /reports/recent API every minute, compares
    the response with report_confirmations, and returns the data for matched reports.

    Args:
        report_confirmations (dict): A dictionary where keys are domain names and values
                            are dictionaries containing report information, including "id".

    Returns:
        list or None: A list of matched report data dictionaries,
                     or None if an error occurs or the timeout is reached.
    """

    # Extracts the "id" values and their corresponding domain names from a dictionary representing report data, and returns a dictionary mapping IDs to domains.
    report_confirmation_ids = {}
    for domain, report_info in report_confirmations.items():
        report_id = report_info["id"]
        report_confirmation_ids[report_id] = domain

    # Set up API Request
    url = "https://api.securityscorecard.io/reports/recent"
    headers = {
        "Authorization": f"Token {api_token}",
        "accept": "application/json"
    }

    matched_receipts = set()
    matched_report_data = []  # List to store data for matched reports

    start_time = time.time()
    timeout = 60 * 60  # 1 hour timeout.

    # Polls the API to match generated reports with requested reports and retrieve their details.
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Iterates through API report data, identifying and storing matched reports.
            for report in data.get("entries", []):
                receipt_id = report.get("id")
                download_url = report.get("download_url")
                if receipt_id and receipt_id in report_confirmation_ids and download_url:
                    matched_receipts.add(receipt_id)
                    matched_report_data.append(report)

            # Checks if all keys of report_confirmation_ids are matched
            if set(report_confirmation_ids.keys()) == matched_receipts:
                print_to_program(f"{len(report_confirmation_ids)} Reports Successfully Finished Generating")
                return matched_report_data

            # Get the domains that are still waiting:
            waiting_domains = [report_confirmation_ids[receipt_id] for receipt_id in report_confirmation_ids.keys() if receipt_id not in matched_receipts]

            print_to_program(f"Matched {len(matched_receipts)} of {len(report_confirmation_ids)} receipts. Checking again in 1 minute...")
            print_to_program(f"Waiting on domains: {waiting_domains}")
            matched_report_data = [] # clear reports for next fetch
            time.sleep(60)  # Wait for 1 minute

        except requests.exceptions.RequestException as e:
            print_to_program(f"Error fetching recent reports: {e}")
            if response is not None:
                try:
                    print_to_program(f"Response Body: {response.json()}")
                except json.JSONDecodeError:
                    print_to_program(f"Response Text: {response.text}")
            return None
        except json.JSONDecodeError as e:
            print_to_program(f"Error decoding JSON response: {e}")
            if response is not None:
                print_to_program(f"Response Text: {response.text}")
            return None

    print_to_program("Timeout reached. Not all report receipts were matched.")
    return None

def download_and_zip_reports(report_data, report_format, zip_filename, language):
    """
    Downloads reports (PDF or JSON) from a list of URLs within the provided report data, optionally appending a language tag to the download url, and zips them.

    Args:
        report_data (list): A list of dictionaries, where each dictionary
                            contains report information, including "download_url".
        report_format (str): The format for the downloaded reports: "pdf" or "json".
        zip_filename (str): The name of the output zip file.
        language (str): The language tag to append to the download url. "Default" will not append any language tag.
    """

    # Get the current date in YYYY-MM-DD format
    current_date = datetime.date.today().strftime("%Y-%m-%d")
    zip_filename_with_date = f"{zip_filename}-{current_date}.zip"

    try:
        with zipfile.ZipFile(zip_filename_with_date, 'w') as zipf:
            print_to_program(f"{len(report_data)} reports to be downloaded.")
            for report in report_data:
                try:
                    # Determine the correct download URL based on report_format
                    if report_format == "json":
                        download_url = report.get("data_download_url")
                    else:  # Default to "pdf"
                        download_url = report.get("download_url")

                    if not download_url:
                        print_to_program(f"Skipping report: Missing 'download_url' or 'data_download_url'")
                        continue  # Skip to the next report if download_url is missing

                    headers = {"Authorization": f"Bearer {api_token}"}
                    response = requests.get((f"{download_url}?lng={language}" if language != "default" else download_url), headers=headers, stream=True)
                    response.raise_for_status()  # Check for HTTP errors

                    # Extract the filename from the download_url (or use a default)
                    filename = os.path.basename(download_url)
                    if not filename:
                        filename = f"report_{report_data.index(report)}.{report_format.lower()}"  # Default name

                    # Write the PDF content to the zip file
                    zipf.writestr(filename, response.content)
                    print_to_program(f"Downloaded and added: {filename}")
                except requests.exceptions.RequestException as e:
                    print_to_program(f"Error downloading {download_url}: {e}")
                except Exception as e:
                    print_to_program(f"An unexpected error occurred: {e}")

        print_to_program(f"Successfully created zip file: {zip_filename_with_date}")

    except Exception as e:
        print_to_program(f"Error creating zip file: {e}")

def create_gui():
    """Creates the Tkinter GUI."""

    window = tk.Tk()
    window.title("Get Summary Reports for all companies in a Portfolio")

    # API Token
    api_token_label = tk.Label(window, text="API Token:")
    api_token_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
    api_token_entry = tk.Entry(window, width=40)
    api_token_entry.grid(row=0, column=1, padx=5, pady=5)

    # Portfolio ID
    portfolio_id_label = tk.Label(window, text="Portfolio ID:")
    portfolio_id_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
    portfolio_id_entry = tk.Entry(window, width=40)
    portfolio_id_entry.grid(row=1, column=1, padx=5, pady=5)

    # File Format
    file_format_label = tk.Label(window, text="File Format:")
    file_format_label.grid(row=2, column=0, sticky="w", padx=5, pady=5)
    file_format_options = ["pdf", "json"]
    file_format_var = tk.StringVar(window)
    file_format_var.set(file_format_options[0])  # Default value is pdf
    file_format_dropdown = ttk.Combobox(window, textvariable=file_format_var, values=file_format_options, state="readonly")
    file_format_dropdown.grid(row=2, column=1, padx=5, pady=5)

    # Branding Decision
    branding_label = tk.Label(window, text="Branding Decision:")
    branding_label.grid(row=3, column=0, sticky="w", padx=5, pady=5)
    branding_options = [
        "SecurityScorecard",
        "Your Company and SecurityScorecard",
        "Your Company Only",
    ]
    branding_var = tk.StringVar(window)
    branding_var.set(branding_options[0])  # Default value
    branding_dropdown = ttk.Combobox(window, textvariable=branding_var, values=branding_options, state="readonly")
    branding_dropdown.grid(row=3, column=1, padx=5, pady=5)

    # File Name
    prepopulated_text = file_name
    file_name_label = tk.Label(window, text="File Name for ZIP:")
    file_name_label.grid(row=4, column=0, sticky="w", padx=5, pady=5)
    file_name_entry = tk.Entry(window, width=40)
    file_name_entry.grid(row=4, column=1, padx=5, pady=5)
    file_name_entry.insert(0, prepopulated_text)

    # Language
    language_label = tk.Label(window, text="Language:")
    language_label.grid(row=5, column=0, sticky="w", padx=5, pady=5)
    language_options = [
        "default",
        "en-US",
        "es-ES",
        "pt-BR",
        "pt-PT",
        "de-DE",
        "fr-FR",
        "ja-JP",
        "zh-CN",
        "zh-TW",
    ]
    language_var = tk.StringVar(window)
    language_var.set(language_options[0])  # Default value
    language_dropdown = ttk.Combobox(window, textvariable=language_var, values=language_options, state="readonly")
    language_dropdown.grid(row=5, column=1, padx=5, pady=5)

    # Text Area
    global text_area
    log_label = tk.Label(window, text="Logs:")
    log_label.grid(row=7, column=0, sticky="w", padx=5, pady=5)
    text_area = tk.Text(window, height=15, width=50, state="disabled") #disabled state.
    text_area.grid(row=8, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
    print_to_textarea("All logs will load here once program finishes.")
    print_to_textarea("Refer to your terminal for live log updates.")

    #configure row and column to expand.
    window.grid_rowconfigure(7, weight=1)
    window.grid_columnconfigure(1, weight=1)

    # Function to get input values and start script
    def generate_reports():
        api_token_input = api_token_entry.get()
        portfolio_id_input = portfolio_id_entry.get()
        file_format_input = file_format_var.get()
        branding_input = branding_var.get()
        file_name_input = file_name_entry.get()
        language_input = language_var.get()

        # Call your script's function with the retrieved values

        branding_map = {
            "SecurityScorecard": "securityscorecard",
            "Your Company and SecurityScorecard": "company_and_securityscorecard",
            "Your Company Only": "company"
        }

        # map branding to API parameters
        branding_input = branding_map.get(branding_input, "securityscorecard") # defaults to securityscorecard.        

        main(api_token_input, portfolio_id_input, file_format_input, branding_input, file_name_input, language_input)

    # Run Button
    run_button = tk.Button(window, text="Generate Reports", command=generate_reports) # Connect the button to the function
    run_button.grid(row=6, column=1, pady=10)

    window.mainloop()

def print_to_textarea(message):
    """Inserts a message into the GUI log textarea."""
    global text_area  # Access the global text_area variable
    if text_area:
        text_area.config(state="normal")
        text_area.insert(tk.END, message + "\n")
        text_area.see(tk.END)
        text_area.config(state="disabled")

def print_to_program(message):
    # print messages to both terminal and GUI logging textarea.
    print(message)
    print_to_textarea(message)

if __name__ == "__main__":
    create_gui()