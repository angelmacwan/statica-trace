# Production Deployment Guide (Linode / Ubuntu)

This guide provides step-by-step instructions for deploying the **Statica Trace** application to production on a Virtual Private Server (VPS) such as Linode, running **Ubuntu 24.04 LTS** (or 22.04 LTS).

---

## 🏛️ Architecture Overview

The production deployment runs both the frontend and backend on the same virtual machine using a reverse-proxy topology. This simplifies SSL termination, avoids CORS issues, and provides high performance:

```
[Client Web Browser]
         │
         ▼ (HTTPS: 443)
┌──────────────────────────────────────────────┐
│                  Nginx                       │
│  ├─ /v1/*, /healthz  ──► Proxy to Uvicorn    │
│  └─ Static Files     ──► Serve from /dist    │
└──────────────────────────────────────────────┘
         │
         ├─► [Uvicorn (FastAPI)] (Port 8000)
         │        │
         │        ▼ (PostgreSQL Async Connection)
         └─► [PostgreSQL Database] (Port 5432)
```

---

## 📋 Prerequisites & Linode Provisioning

1. **Deploy a Linode Instance**:
   - Create a new Linode using the **Ubuntu 24.04 LTS** image.
   - Select a plan (a **Shared CPU - 1 GB or 2 GB RAM** plan is sufficient for small to medium trace volumes).
   - Set up an SSH key for secure access.

2. **Domain Name Setup**:
   - Point an `A` record from your domain or subdomain (e.g., `statica.example.com`) to the public IP address of your Linode.

3. **Server Security & Firewall**:
   Log in as `root` via SSH, create a non-root user with `sudo` privileges, and enable a basic firewall:
   ```bash
   # Add deployment user
   adduser deploy
   usermod -aG sudo deploy

   # Switch to the deploy user
   su - deploy

   # Configure Firewall
   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   sudo ufw allow ssh
   sudo ufw allow http
   sudo ufw allow https
   sudo ufw enable
   ```

---

## 💾 1. PostgreSQL Database Setup

Statica Trace uses PostgreSQL in production. The connection requires the async driver `asyncpg`.

1. **Install PostgreSQL**:
   ```bash
   sudo apt update
   sudo apt install -y postgresql postgresql-contrib
   ```

2. **Configure Database and User**:
   Generate a secure, random password for the database user:
   ```bash
   # Access PostgreSQL prompt as postgres superuser
   sudo -u postgres psql
   ```
   Inside the SQL shell, execute:
   ```sql
   -- Create production database
   CREATE DATABASE statica_trace;

   -- Create database user with a secure password
   CREATE USER statica_user WITH PASSWORD 'YOUR_SECURE_PASSWORD_HERE';

   -- Grant permissions
   GRANT ALL PRIVILEGES ON DATABASE statica_trace TO statica_user;

   -- Exit the prompt
   \q
   ```

3. **Test the Connection**:
   You can verify the credentials locally:
   ```bash
   psql -h localhost -U statica_user -d statica_trace
   ```

---

## ⚙️ 2. Backend Service Deployment

We deploy the FastAPI application using `uvicorn` managed by a `systemd` unit file to keep it running in the background and restart it on system failures.

1. **Prepare Directories**:
   Clone the repository to `/var/www/statica-trace` and adjust ownership so the `deploy` user owns it, but the web server (`www-data`) has execution/read rights where needed:
   ```bash
   sudo mkdir -p /var/www
   sudo chown -R deploy:deploy /var/www
   cd /var/www
   git clone https://github.com/your-username/statica-trace.git
   cd statica-trace
   ```

2. **Set Up Python Virtual Environment**:
   ```bash
   sudo apt install -y python3-pip python3-venv build-essential
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Production Dependencies**:
   Instead of installing all dev dependencies, install the exact libraries required to run the FastAPI backend, along with the async Postgres driver (`asyncpg`):
   ```bash
   pip install --upgrade pip
   pip install fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" asyncpg pydantic httpx
   ```

4. **Create Systemd Service**:
   Create a service configuration at `/etc/systemd/system/statica-backend.service`:
   ```bash
   sudo nano /etc/systemd/system/statica-backend.service
   ```
   Paste the following configuration, substituting your actual database password:
   ```ini
   [Unit]
   Description=Statica Trace FastAPI Backend
   After=network.target postgresql.service

   [Service]
   User=deploy
   Group=deploy
   WorkingDirectory=/var/www/statica-trace
   Environment="DATABASE_URL=postgresql+asyncpg://statica_user:YOUR_SECURE_PASSWORD_HERE@localhost:5432/statica_trace"
   Environment="PYTHONUNBUFFERED=1"
   ExecStart=/var/www/statica-trace/venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

5. **Start and Enable the Backend Service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start statica-backend
   sudo systemctl enable statica-backend
   ```

6. **Check Service Status**:
   Verify that the backend service is active and running:
   ```bash
   sudo systemctl status statica-backend
   ```

---

## 🎨 3. Frontend Build & Static Serving

The React frontend compiles into optimized static files (HTML, JS, CSS) using Vite.

1. **Install Node.js (V20 LTS)**:
   ```bash
   curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
   sudo apt install -y nodejs
   ```

2. **Build the Frontend Assets**:
   Since Nginx will route `/v1/*` API calls to the local FastAPI port on the same domain, you do not need to configure a separate backend subdomain. The relative fallback URL logic handles it automatically.
   
   If you decide to host the API on a separate subdomain later, build it with `VITE_API_BASE` pointed to that domain.
   ```bash
   cd /var/www/statica-trace/frontend
   npm install
   
   # Compile frontend assets
   VITE_API_BASE="" npm run build
   ```
   This generates the static bundle inside `/var/www/statica-trace/frontend/dist`.

---

## 🌐 4. Nginx Configuration

Nginx will serve the frontend static files directly and act as a reverse proxy for backend API routes.

1. **Install Nginx**:
   ```bash
   sudo apt install -y nginx
   ```

2. **Configure Nginx Site**:
   Remove the default site configuration and create a new one:
   ```bash
   sudo rm /etc/nginx/sites-enabled/default
   sudo nano /etc/nginx/sites-available/statica-trace
   ```
   Paste the following configuration (replace `statica.example.com` with your actual domain):
   ```nginx
   server {
       listen 80;
       server_name statica.example.com;

       # Redirect all HTTP requests to HTTPS (after Certbot setup)
       location / {
           return 301 https://$host$request_uri;
       }
   }

   server {
       listen 443 ssl http2;
       server_name statica.example.com;

       # SSL parameters (Certbot will manage these, but we declare basic fields)
       ssl_certificate /etc/letsencrypt/live/statica.example.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/statica.example.com/privkey.pem;

       # Frontend Static Files
       location / {
           root /var/www/statica-trace/frontend/dist;
           index index.html;
           try_files $uri $uri/ /index.html;
       }

       # Backend API proxy
       location /v1/ {
           proxy_pass http://127.0.0.1:8000/v1/;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
           
           # Forward visitor IPs for accurate logs & rate limits
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       # Backend Health Check
       location /healthz {
           proxy_pass http://127.0.0.1:8000/healthz;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

3. **Enable Nginx Configuration**:
   ```bash
   sudo ln -s /etc/nginx/sites-available/statica-trace /etc/nginx/sites-enabled/
   ```

4. **Verify and Restart Nginx**:
   Ensure there are no syntax errors in the configuration, then restart the service:
   ```bash
   sudo nginx -t
   sudo systemctl restart nginx
   ```

---

## 🔒 5. SSL / HTTPS with Let's Encrypt

1. **Install Certbot**:
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   ```

2. **Obtain SSL Certificate**:
   Run Certbot to request a free certificate and automatically configure Nginx SSL routing:
   ```bash
   sudo certbot --nginx -d statica.example.com
   ```
   Follow the prompts to configure email reminders and accept terms. Certbot will automatically edit your Nginx config to load the Let's Encrypt certificates.

3. **Verify Renewal Cron Job**:
   Let's Encrypt certificates expire in 90 days. Certbot automatically adds a system cron job to handle renewal. Test it with:
   ```bash
   sudo certbot renew --dry-run
   ```

---

## 🚀 6. Verification and First Run

1. **Verify Backend Status**:
   Visit `https://statica.example.com/healthz` in your browser or run:
   ```bash
   curl -I https://statica.example.com/healthz
   ```
   It should return an HTTP 200 response with `{"status": "ok"}`.

2. **Log In and Initialize Project**:
   - Load the dashboard in your web browser: `https://statica.example.com`.
   - Enter a name for your first project (e.g. `Production Agent Group`).
   - The UI will communicate with the backend, write your new project record to the PostgreSQL database, and return a unique API Key.
   - Save your API key.

3. **Verify Trace Ingestion**:
   In your client application, set the backend API endpoint to point to your new live server:
   ```python
   from agentreplay.otel_exporter import AgentReplayOTelExporter
   
   exporter = AgentReplayOTelExporter(
       api_key="YOUR_PRODUCTION_API_KEY",
       endpoint="https://statica.example.com/v1/ingest"
   )
   ```
   Run a quick trace workflow on your local machine. It should post successfully to the server, and the new trace should appear instantly on the live dashboard.

---

## 🧹 Maintenance and Updates

### Pulling Updates

When updates are pushed to the main repository, update your production instance using these steps:

```bash
cd /var/www/statica-trace
git pull origin main

# Re-build frontend
cd frontend
npm install
VITE_API_BASE="" npm run build

# Restart services
sudo systemctl restart statica-backend
sudo systemctl restart nginx
```

### Viewing Logs

If you encounter issues, inspect the logs using `journalctl` (for the backend) or check the Nginx error logs:

```bash
# Backend live logs
sudo journalctl -u statica-backend -f

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```
