---
title: Sale Purchase Hub
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Sale & Purchase Hub

A Flask-based web application for managing sales, purchases, and syncing them with Google Sheets.

## Deployment on Hugging Face Spaces

This repository is pre-configured to be deployed on **Hugging Face Spaces** using Docker.

- **SDK:** Docker
- **Port:** 7860 (exposed automatically)
- **RAM:** 16GB (Free tier)
- **Storage:** Supports persistent storage mount at `/data`

## Running Locally

To run this application locally:

1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python app.py
   ```

3. Open in browser: `http://localhost:5000`
