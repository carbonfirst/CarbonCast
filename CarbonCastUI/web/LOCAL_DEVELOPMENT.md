# Local Development

## Installation Steps

### 1. Navigate to the web directory
```bash
cd CarbonCastUI/web
```

### 2. Install dependencies
```bash
npm install
```

### 3. Configure environment variables
Create a `.env` file in the `CarbonCastUI/web/` directory:
```bash
cp .env.example .env
```

The `.env` file should contain:
```
VITE_API_BASE_URL=http://localhost:8000
```

## Starting the Development Server
```bash
npm run dev
```

The application will be available at **http://localhost:5173/** with hot module replacement (HMR) enabled.