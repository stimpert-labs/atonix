# Atonix Python Client - Examples

This directory contains practical examples demonstrating how to use the Atonix Python client library.

## Setup

Before running these examples, ensure you have:

1. **Installed the atonix package**:
   ```bash
   pip install atonix
   ```

2. **Set up authentication**:
   
   Set environment variables:
   ```bash
   export ATONIX_API_KEY="your-api-key-here"
   export ATONIX_PRIVATE_KEY_PATH="/path/to/your/private_key.pem"
   export ATONIX_PRIVATE_KEY_PASSWORD="your-password" # if key is encrypted, skip if not
   ```

   Or on Windows:
   ```powershell
   $env:ATONIX_API_KEY="your-api-key-here"
   $env:ATONIX_PRIVATE_KEY_PATH="C:\path\to\your\private_key.pem"
   $env:ATONIX_PRIVATE_KEY_PASSWORD="your-password" # if key is encrypted, skip if not
   ```

## Examples

### 1. [basic_usage.py](basic_usage.py)
Demonstrates basic asset retrieval and navigation through the asset hierarchy.

**Run**: `python examples/basic_usage.py`

### 2. [process_data_query.py](process_data_query.py)
Shows how to query time-series process data for tags over a date range.

**Run**: `python examples/process_data_query.py`

### 3. [issue_management.py](issue_management.py)
Demonstrates creating, updating, and managing issues in Atonix.

**Run**: `python examples/issue_management.py`

### 4. [model_detailed_info.py](model_detailed_info.py)
Shows how to drill down into a specific model to get its configuration, current alert state, and recent actions.

**Run**: `python examples/model_detailed_info.py`

### 5. [asset_model_summary.py](asset_model_summary.py)
Demonstrates aggregating model information at the asset level, including health summaries and combined action feeds for an entire asset hierarchy.

**Run**: `python examples/asset_model_summary.py`

## Notes

- These examples use live API endpoints and require valid credentials
- Modify asset IDs, tag IDs, and date ranges as needed for your environment
- All examples include error handling and logging for demonstration purposes

## Additional Resources

- [README.md](../README.md) - Main library documentation
- [AGENTS.md](../AGENTS.md) - Development guide and contributor/agent conventions
- [API Documentation](https://oi.atonix.com/help) - Official Atonix API docs
