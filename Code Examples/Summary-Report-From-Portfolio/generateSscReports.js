const axios = require('axios');
const AdmZip = require('adm-zip');
const path = require('path');
const fs = require('fs');

// Add your API token and portfolio ID here
const apiToken = "";
const portfolioId = "";

// Optional parameters

/**
 * Format for the downloaded reports: "pdf" or "json". PDF is populated below as default.
 * @type {"pdf" | "json"}
 */
const reportFormat = "json";

/**
 * Values for branding:
 *     securityscorecard (default) = reports are only displaying SecurityScorecard's logo
 *     company_and_securityscorecard = your company's logo will be used in conjunction with Security Scorecard's.
 *     company = reports are only displaying your company's logo
 * @type {string}
 */
const branding = "company";

/**
 * File name for your reports.
 * Format is: "{file_name}-YYYY-MM-DD.zip"
 * @type {string}
 */
const fileName = "downloaded-reports";

/**
 * Language code for the downloaded report. Language codes can be found on API Reference. Leave as "default" if you do not wish to specify a language.
 * @type {string}
 */
const language = "default";

async function main() {
    const portfolioCompanies = await getPortfolioCompanies(portfolioId);
    if (!portfolioCompanies) return;

    const reportConfirmations = await generateSummaryReports(portfolioCompanies, branding);
    const completedReports = await waitForCompletedReports(reportConfirmations);

    if (completedReports) {
        await downloadAndZipReports(completedReports, reportFormat, fileName, language);
    }
}

/**
 * @param {string} portfolioId
 * @returns {Promise<Array<Entry>>} Returns an array of companies in the portfolio.
 */
async function getPortfolioCompanies(portfolioId) {
    try {
        const url = `https://api.securityscorecard.io/portfolios/${portfolioId}/companies`;

        const response = await axios.get(url, {
            headers: {
                'Authorization': `Token ${apiToken}`,
                'accept': 'application/json; charset=utf-8'
            }
        });
        /**
         * @type {PortfolioCompanyQueryResponseBody}
         */
        const data = response.data;

        console.log(`Successfully retrieved Portfolio ID: ${portfolioId}`);
        const {entries} = response.data;
        console.log(`${entries.length} Companies Retrieved in Portfolio.`);
        return entries;
    } catch (error) {
        console.error('Error fetching portfolio companies:', error.message);
        if (error.response) {
            console.error('Response Body:', error.response.data);
        }
        return null;
    }
}

/**
 *
 * @param {Entry[]} portfolioCompanies
 * @param {string} branding
 * @returns {Promise<{[domain: string]: SummaryReportResponse}>}
 */
async function generateSummaryReports(portfolioCompanies, branding) {
    const url = "https://api.securityscorecard.io/reports/summary";
    const results = {};

    for (const company of portfolioCompanies) {
        try {
            /**
             * @type {SummaryReportResponse}
             */
            const response = await axios.post(url, {
                scorecard_identifier: company.domain,
                branding
            }, {
                headers: {
                    'Authorization': `Token ${apiToken}`,
                    'accept': 'application/json; charset=utf-8',
                    'content-type': 'application/json'
                }
            });

            results[company.domain] = response.data;
            console.log(`Successfully requested report generation for: ${company.domain}`);
        } catch (error) {
            console.error(`Error generating report for ${company.domain}:`, error.message);
            results[company.domain] = null;
        }
    }

    console.log(`${Object.keys(results).length} Reports successfully requested for generation.`);
    return results;
}

/**
 * Waits for the report generation to complete and returns the report data.
 * @param reportConfirmations
 * @returns {Promise<null|*[]>}
 */
async function waitForCompletedReports(reportConfirmations) {
    const reportConfirmationIds = {};
    Object.entries(reportConfirmations).forEach(([domain, reportInfo]) => {
        if (reportInfo) reportConfirmationIds[reportInfo.id] = domain;
    });

    const url = "https://api.securityscorecard.io/reports/recent";
    const startTime = Date.now();
    const timeout = 60 * 60 * 1000; // 1 hour timeout

    while (Date.now() - startTime < timeout) {
        try {
            const response = await axios.get(url, {
                headers: {
                    'Authorization': `Token ${apiToken}`,
                    'accept': 'application/json'
                }
            });

            const matchedReceipts = new Set();
            const matchedReportData = [];

            for (const report of response.data.entries) {
                if (report.id && reportConfirmationIds[report.id] && report.download_url) {
                    matchedReceipts.add(report.id);
                    matchedReportData.push(report);
                }
            }

            if (matchedReceipts.size === Object.keys(reportConfirmationIds).length) {
                console.log(`${matchedReceipts.size} Reports Successfully Finished Generating`);
                return matchedReportData;
            }

            const waitingDomains = Object.entries(reportConfirmationIds)
                .filter(([id]) => !matchedReceipts.has(id))
                .map(([, domain]) => domain);

            console.log(`Matched ${matchedReceipts.size} of ${Object.keys(reportConfirmationIds).length} receipts. Checking again in 1 minute...`);
            console.log(`Waiting on domains: ${waitingDomains}`);

            await new Promise(resolve => setTimeout(resolve, 60000)); // Wait 1 minute
        } catch (error) {
            console.error('Error fetching recent reports:', error.message);
            return null;
        }
    }

    console.log("Timeout reached. Not all report receipts were matched.");
    return null;
}

/**
 * Downloads the reports and zips them.
 * @param reportData
 * @param reportFormat
 * @param zipFilename
 * @param language
 * @returns {Promise<void>}
 */
async function downloadAndZipReports(reportData, reportFormat, zipFilename, language) {
    const currentDate = new Date().toISOString().split('T')[0];
    const zipFilenameWithDate = `${zipFilename}-${currentDate}.zip`;
    const zip = new AdmZip();

    console.log(`${reportData.length} reports to be downloaded.`);

    for (const report of reportData) {
        try {
            const downloadUrl = reportFormat === "json" ? report.data_download_url : report.download_url;
            if (!downloadUrl) {
                console.log("Skipping report: Missing download URL");
                continue;
            }

            const finalUrl = language !== "default" ? `${downloadUrl}?lng=${language}` : downloadUrl;
            const response = await axios.get(finalUrl, {
                headers: {'Authorization': `Bearer ${apiToken}`},
                responseType: 'arraybuffer'
            });

            const filename = path.basename(downloadUrl) || `report_${reportData.indexOf(report)}.${reportFormat.toLowerCase()}`;
            zip.addFile(filename, response.data);
            console.log(`Downloaded and added: ${filename}`);
        } catch (error) {
            console.error(`Error downloading report:`, error.message);
        }
    }

    zip.writeZip(zipFilenameWithDate);
    console.log(`Successfully created zip file: ${zipFilenameWithDate}`);
}

if (require.main === module) {
    main().catch(console.error);
}


/**
 * @typedef {Object} BusinessImpact
 * @property {string} value
 */

/**
 * @typedef {Object} Entry
 * @property {string} domain
 * @property {string} uuid
 * @property {string} name
 * @property {number} score
 * @property {string} added_date
 * @property {string} grade
 * @property {string} grade_url
 * @property {number} last30days_score_change
 * @property {string} industry
 * @property {string} size
 * @property {string[]} products
 * @property {number} products_count
 * @property {BusinessImpact} [business_impact]
 */

/**
 * @typedef {Object} PortfolioCompanyQueryResponseBody
 * @property {Entry[]} entries
 * @property {number} total
 */

/**
 * @typedef {object} SummaryReportResponse
 * @property {number} status
 * @property {string} statusText
 * @property {SummaryReportResponseBody} data
 * @property {object} headers
 * @property {string} headers['content-type']
 * @property {number} headers['content-length']
 * @property {object} config
 * @property {object} request
 */


/** @typedef {object} SummaryReportResponseBody
 * @property {object} params
 * @property {string} params.domain
 * @property {string} params.branding
 * @property {string} format
 * @property {string} title
 * @property {string} id
 * @property {string} report_type
 * @property {string} created_at
 * @property {boolean} is_new
 */
