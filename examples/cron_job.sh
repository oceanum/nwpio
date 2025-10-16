#!/bin/bash
# Example cron job script for automated NWP data download and processing
# Add to crontab: 0 */6 * * * /path/to/cron_job.sh

set -e

# Configuration
CONFIG_FILE="/path/to/config.yaml"
LOG_DIR="/path/to/logs"
VENV_PATH="/path/to/venv"

# Activate virtual environment
source "${VENV_PATH}/bin/activate"

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# Generate log filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/nwp_download_${TIMESTAMP}.log"

# Run the workflow
echo "Starting NWP download workflow at $(date)" | tee -a "${LOG_FILE}"

nwp-download run --config "${CONFIG_FILE}" 2>&1 | tee -a "${LOG_FILE}"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "Workflow completed successfully at $(date)" | tee -a "${LOG_FILE}"
else
    echo "Workflow failed with exit code $EXIT_CODE at $(date)" | tee -a "${LOG_FILE}"
    # Optional: Send alert email
    # echo "NWP download failed. Check ${LOG_FILE}" | mail -s "NWP Download Failed" admin@example.com
fi

# Optional: Clean up old logs (keep last 30 days)
find "${LOG_DIR}" -name "nwp_download_*.log" -mtime +30 -delete

exit $EXIT_CODE
