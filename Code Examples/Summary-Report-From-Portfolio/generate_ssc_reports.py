# Get Summary Reports for all companies in a Portfolio
import json
import requests

import time

import zipfile
import os

import datetime

# Add your API token and portfolio ID here
api_token = ""
portfolio_id = ""

# Optional parameters. Can leave variables as is if no personalization is desired.
"""
Format for the downloaded reports: "pdf" or "json". PDF is populated below as default.
"""
report_format = "json"

"""
Values for branding:
    securityscorecard (default) = reports are only displaying SecurityScorecard's logo
    company_and_securityscorecard = your company's logo will be used in conjunction with Security Scorecard's.
    company = reports are only displaying your company's logo
"""
branding = "company"

"""
File name for your reports. 
Format is: "{file_name}-YYYY-MM-DD.zip"
"""
file_name = "downloaded-reports"

"""
Language code for the downloaded report. Language codes can be found on API Reference. Leave as "default" if you do not wish to specify a language.
"""
language = "default"

def main():

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
        print(f"Successfully retrieved Portfolio ID: {portfolio_id}")
        print(f"{len(response_dict)} Companies Retrieved in Portfolio.")
        return response_dict
    except requests.exceptions.RequestException as e:
        print(f"Error fetching portfolio companies: {e}")
        if response is not None:
            try:
                print(f"Response Body: {response.json()}")
            except json.JSONDecodeError:
                print(f"Response Text: {response.text}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        if response is not None:
            print(f"Response Text: {response.text}")
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
            print(f"Successfully requested report generation for: {company_domain}")

        except requests.exceptions.RequestException as e:
            print(f"Error generating report for {company_domain}: {e}")
            results[company_domain] = None
            if response is not None:
                try:
                    print(f"Response Body: {response.json()}")
                except json.JSONDecodeError:
                    print(f"Response Text: {response.text}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response for {company_domain}: {e}")
            results[company_domain] = None
            if response is not None:
                print(f"Response Text: {response.text}")
    
    print(f"{len(results)} Reports successfully requested for generation.")
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
                print(f"{len(report_confirmation_ids)} Reports Successfully Finished Generating")
                return matched_report_data

            # Get the domains that are still waiting:
            waiting_domains = [report_confirmation_ids[receipt_id] for receipt_id in report_confirmation_ids.keys() if receipt_id not in matched_receipts]

            print(f"Matched {len(matched_receipts)} of {len(report_confirmation_ids)} receipts. Checking again in 1 minute...")
            print(f"Waiting on domains: {waiting_domains}")
            matched_report_data = [] # clear reports for next fetch
            time.sleep(60)  # Wait for 1 minute

        except requests.exceptions.RequestException as e:
            print(f"Error fetching recent reports: {e}")
            if response is not None:
                try:
                    print(f"Response Body: {response.json()}")
                except json.JSONDecodeError:
                    print(f"Response Text: {response.text}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response: {e}")
            if response is not None:
                print(f"Response Text: {response.text}")
            return None

    print("Timeout reached. Not all report receipts were matched.")
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
            print(f"{len(report_data)} reports to be downloaded.")
            for report in report_data:
                try:
                    # Determine the correct download URL based on report_format
                    if report_format == "json":
                        download_url = report.get("data_download_url")
                    else:  # Default to "pdf"
                        download_url = report.get("download_url")
                    
                    if not download_url:
                        print(f"Skipping report: Missing 'download_url' or 'data_download_url'")
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
                    print(f"Downloaded and added: {filename}")
                except requests.exceptions.RequestException as e:
                    print(f"Error downloading {download_url}: {e}")
                except Exception as e:
                    print(f"An unexpected error occurred: {e}")

        print(f"Successfully created zip file: {zip_filename_with_date}")

    except Exception as e:
        print(f"Error creating zip file: {e}")

if __name__ == "__main__":
    main()