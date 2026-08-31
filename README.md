# AI Predictive Maintenance - Enhanced Edition (with real email alerts)

Monitors multiple machines (M01-M03), four simulated sensors per machine,
uses a Random Forest model to predict failure risk, shows a live
Streamlit dashboard, and **sends a real email** to the maintenance team
whenever a machine's predicted failure risk crosses a threshold.

## What's new vs. the original version
- **Real SMTP email alerts** (`alerts.py`) when a machine hits "HIGH FAILURE RISK".
- **Per-machine cooldown** so the same machine can't spam your inbox every
  few seconds while it stays unhealthy (configurable, default 15 minutes).
- **Alert history table** (`alert_log`) in PostgreSQL + a panel in the
  dashboard showing every alert attempt, sent or failed, and why.
- **Credentials moved out of source code** into a local `.env` file
  (via `python-dotenv`) instead of being hard-coded in `config.py`.
- **`test_email.py`** — a one-command way to verify your SMTP setup works
  before trusting it inside the live app.
- Schema creation is automatic (`ensure_schema()`), so you no longer have
  to run the SQL file by hand (though you still can).

## Setup

1. **Install PostgreSQL** and create the database:
   ```
   psql -U postgres -f postgres_setup.sql
   ```
   (Or just let the app create the tables automatically on first run.)

2. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

3. **Configure secrets**
   ```
   cp .env.example .env
   ```
   Then edit `.env` and fill in:
   - Your PostgreSQL host/user/password.
   - Your SMTP settings. For Gmail:
     1. Turn on 2-Step Verification on the sending Gmail account.
     2. Create an **App Password** at
        https://myaccount.google.com/apppasswords
     3. Use that 16-character app password as `SMTP_PASSWORD` (your normal
        Gmail password will not work for SMTP login).
   - `ALERT_RECIPIENTS` — comma-separated list of who should get the alerts.
   - `ALERT_RISK_THRESHOLD` — risk % (0-100) that triggers an email
     (default 60).
   - `ALERT_COOLDOWN_MINUTES` — minimum time between two alerts for the
     same machine (default 15).

   Other SMTP providers work too (Outlook: `smtp.office365.com:587`,
   Yahoo: `smtp.mail.yahoo.com:587`, or your company's mail server) — just
   change `SMTP_HOST` / `SMTP_PORT` accordingly.

4. **Test your email setup**
   ```
   python test_email.py
   ```
   You should see "Test email sent successfully" and receive it in your
   inbox. Fix any errors it reports before moving on.

5. **Train the model**
   ```
   python train_model.py
   ```

6. **Run the simulator** (Terminal 1)
   ```
   python sensor_simulator.py
   ```

7. **Run the dashboard** (Terminal 2)
   ```
   streamlit run app.py
   ```

The simulator mostly generates normal readings with occasional abnormal
spikes. When a machine's predicted risk reaches the threshold, the
dashboard will show "🚨 Maintenance recommended" **and** trigger a real
email to everyone in `ALERT_RECIPIENTS` (subject to the cooldown).

## Disabling email alerts temporarily
Set `EMAIL_ALERTS_ENABLED=false` in `.env` — the dashboard will keep
working exactly as before, just without sending mail. This is useful
for demos where you don't want to trigger real emails.

## Files
| File | Purpose |
|---|---|
| `app.py` | Streamlit dashboard, prediction, wires up alerts |
| `alerts.py` | Builds and sends the SMTP email, applies cooldown, logs result |
| `database.py` | PostgreSQL access: readings + alert log |
| `config.py` | Loads all settings from `.env` |
| `train_model.py` | Trains and saves the Random Forest model |
| `sensor_simulator.py` | Generates fake sensor data into PostgreSQL |
| `test_email.py` | Standalone SMTP connectivity/delivery check |
| `postgres_setup.sql` | Manual schema creation (optional, auto-run otherwise) |
| `.env.example` | Template for your local `.env` (never commit the real `.env`) |
