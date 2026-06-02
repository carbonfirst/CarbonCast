# CarbonCast Remote Server Deployment Guide
## Deployment on asouza.io Container

## 🔐 Initial Connection & Setup

### Step 1: SSH Connection
Connect to the remote container:
```bash
ssh tanush@asouza.io -p 2222
```

### Step 2: Password Change
**current password:** ``

Change your password immediately after first login:
```bash
passwd
```
Enter the current password (123change), then enter your new password twice.

---

## 📦 Repository Setup

### Step 3: Clone Repositories
Navigate to the base directory and clone both repositories:

```bash
# Create and navigate to base directory in your home folder
mkdir -p ~/carboncast
cd ~/carboncast

# Clone CarbonCast API repository (using django_apis_sqlite branch)
git clone --depth 1 -b django_apis_sqlite https://github.com/carbonfirst/CarbonCast.git

# Clone CarbonCastUI repository
git clone --depth 1 https://github.com/carbonfirst/CarbonCastUI.git
```

**Note:** The Django API code is on the `django_apis_sqlite` branch. The UI repository uses the main branch.

---

## 🐍 Python Environment Setup

### Step 4: Create Virtual Environment
```bash
cd ~/carboncast
python3 -m venv venv
source venv/bin/activate
```

### Step 5: Install Python Dependencies
```bash
# Upgrade pip first
pip install --upgrade pip

# Navigate to API directory
cd ~/carboncast/CarbonCast

# Install main requirements if present
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

# Install API-specific requirements
if [ -f src/CarbonCastAPI/requirements.txt ]; then
    pip install -r src/CarbonCastAPI/requirements.txt
fi

# Install core dependencies
pip install django djangorestframework requests numpy pandas
```

---

## 🗄️ Database Setup

### Step 6: Initialize SQLite Database
SQLite is already installed in the container. Set up the database:

```bash
cd ~/carboncast/CarbonCast/src/CarbonCastAPI

# Run database migrations
python3 manage.py migrate
```

---

## 🎨 UI Build & Setup

### Step 7: Build UI for Production

```bash
cd ~/carboncast/CarbonCastUI/web

Follow instructions at https://heynode.com/tutorial/install-nodejs-locally-nvm/ 
to install Node.js using nvm if not already installed.

then run: 

nvm install node

# Install dependencies
npm install

# Install Node.js static file servers (choose one)
npm install -g serve        # Option 1: serve (recommended)
npm install http-server  # Option 2: http-server

# Create .env.production file with the correct API URL
echo "VITE_API_BASE_URL=http://carboncast.duckdns.org:8000" > .env.production

# Build for production (will use .env.production)
npm run build

# Create distribution directory
mkdir -p ~/carboncast/ui-dist

# Copy built files
cp -r dist/* ~/carboncast/ui-dist/
```

**Note:** The API URL is configured via the `VITE_API_BASE_URL` environment variable. For production, we set it to `http://carboncast.duckdns.org:8000` in the `.env.production` file before building.

---

## 🚀 Starting the Services

### Step 8: Start the API Server
**Important:** API runs on port 8000

In one terminal or screen session:
```bash
# Activate virtual environment
source ~/carboncast/venv/bin/activate

# Navigate to API directory
cd ~/carboncast/CarbonCast/src/CarbonCastAPI

# Start Django server on port 8000
python3 manage.py runserver 0.0.0.0:8000
```

### Step 9: Start the UI Server
**Important:** UI runs on port 8001

In another terminal or screen session:

#### Option A: Using Node.js Static Server (Recommended)
```bash
# Using serve (recommended for production)
cd ~/carboncast/ui-dist
serve -s . -l 8001

# OR using http-server
cd ~/carboncast/ui-dist
http-server -p 8001 -a 0.0.0.0
```

#### Option B: Using Vite Preview Server (For Testing)
```bash
# If you want to preview the built application
cd ~/carboncast/CarbonCastUI/web
npm run preview -- --port 8001 --host 0.0.0.0
```

---

## ✅ Verification

### Step 10: Verify Services
Check that both services are accessible:

1. **Website (UI):** http://carboncast.duckdns.org:8001/
2. **REST API:** http://carboncast.duckdns.org:8000/

Test API endpoint:
```bash
# From local machine
curl http://carboncast.duckdns.org:8000/api/

# From within container
curl http://localhost:8000/api/
```
