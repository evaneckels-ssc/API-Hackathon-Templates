# This script retrieves a list of companies from a specific SecurityScorecard portfolio
# and prints key details (Domain, UUID, Name, Score, Grade) for each company.
import requests
import json

# --- Configuration ---
# Replace with your actual API key
api_key = "YOUR_API_KEY"
# Replace with the specific portfolio ID you want to query
portfolio_id = "YOUR_PORTFOLIO_ID"

# --- API Call Setup ---
# Construct the URL for the portfolio companies endpoint
url = f"https://api.securityscorecard.io/portfolios/{portfolio_id}/companies"

# Define the headers required for the API request, including authorization
# This uses the Token authentication scheme as specified.
headers = {
    "accept": "application/json; charset=utf-8",
    "Authorization": f"Token {api_key}"
}

print(f"--- Fetching Companies from Portfolio ID: {portfolio_id} ---")

# --- Execute Request and Process Response (Simplified) ---
# Send a GET request to the specified URL with the defined headers
response = requests.get(url, headers=headers)

# Raise an exception if the API returns an error status code (4xx or 5xx)
response.raise_for_status()

# Parse the JSON response from the API
json_data = response.json()

# --- Print Specific Fields ---
# Check if the 'entries' key exists and is a list before iterating
if 'entries' in json_data and isinstance(json_data['entries'], list):
    if not json_data['entries']:
         print("Portfolio contains no companies.")
    else:
        # Iterate through each company entry in the list
        for entry in json_data['entries']:
            # Extract the desired fields using .get() for safety
            # Provides 'N/A' if a key is missing in a specific entry
            domain = entry.get('domain', 'N/A')
            uuid = entry.get('uuid', 'N/A')
            name = entry.get('name', 'N/A')
            score = entry.get('score', 'N/A')
            grade = entry.get('grade', 'N/A')

            # Print the extracted information for the current company
            print(f"Domain: {domain}")
            print(f"UUID: {uuid}")
            print(f"Name: {name}")
            print(f"Score: {score}")
            print(f"Grade: {grade}")
            print("-" * 20) # Print a separator line for readability
else:
    # Handle cases where the response doesn't contain the expected 'entries' list
    print("Could not find 'entries' list in the API response.")
    print("Full response received:")
    print(json.dumps(json_data, indent=4)) # Print the full response for debugging

print("\n--- Company Fetch Complete ---")
