# 🌐 Public Launch & Cloud Deployment Guide

Step-by-step instructions to deploy your **AI Expense Visualizer** online so anyone can access it publicly on the internet.

---

## ⚡ Option 1: Instant Free Launch with Render (Recommended)

Render offers **100% free cloud hosting** for Python/Flask web services.

### Steps:
1. **Push your code to GitHub**:
   - Initialize git in this project directory (if not already done):
     ```bash
     git init
     git add .
     git commit -m "Initial launch of AI Expense Visualizer"
     ```
   - Create a new repository on [GitHub.com](https://github.com/new) and push your code:
     ```bash
     git remote add origin https://github.com/YOUR_USERNAME/AI_Expense_Visualizer.git
     git branch -M main
     git push -u origin main
     ```

2. **Deploy on Render**:
   - Go to [dashboard.render.com](https://dashboard.render.com/) and Sign Up / Log In with GitHub.
   - Click **New +** &rarr; **Web Service**.
   - Select your GitHub repository `AI_Expense_Visualizer`.
   - Set the following settings:
     - **Name**: `my-ai-expense-visualizer`
     - **Language**: `Python 3`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn wsgi:app`
   - In **Environment Variables**:
     - `DB_TYPE`: `sqlite` (or your MySQL database credentials)
     - `SECRET_KEY`: `your-random-secret-key-2026`
     - *(Optional)* `GEMINI_API_KEY`: `your_gemini_api_key`
   - Click **Create Web Service**.

3. **Your Live Public URL**:
   Within 1–2 minutes, Render will assign you a live HTTPS public domain:
   👉 `https://my-ai-expense-visualizer.onrender.com`

---

## ⚡ Option 2: Instant Public URL with Ngrok (Test Live in 30 Seconds)

If you want to share your live app with friends or test on mobile immediately from your computer:

1. Download [Ngrok](https://ngrok.com/download) or install via terminal:
   ```bash
   winget install ngrok
   ```
2. Start your Flask application:
   ```bash
   python app.py
   ```
3. In a second terminal window, run:
   ```bash
   ngrok http 5000
   ```
4. Copy the generated `https://xxxx.ngrok-free.app` URL and open it on your phone or share with anyone worldwide!

---

## ⚡ Option 3: Deploy on Railway.app

1. Go to [railway.app](https://railway.app/) and log in with GitHub.
2. Click **New Project** &rarr; **Deploy from GitHub repo**.
3. Select `AI_Expense_Visualizer`.
4. Railway will automatically detect the `Procfile` and deploy your app with a public domain!
