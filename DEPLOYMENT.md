# Google Cloud Run Deployment Guide

This guide will help you deploy the Event Scheduling API to Google Cloud Run.

## Prerequisites

1. **Google Cloud Account**: Create one at https://cloud.google.com
2. **Google Cloud CLI**: Install from https://cloud.google.com/sdk/docs/install
3. **Docker** (optional): Only needed for local testing

## Setup Steps

### 1. Initial Google Cloud Setup

```bash
# Login to Google Cloud
gcloud auth login

# Set your project ID (replace with your actual project ID)
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable storage.googleapis.com
```

### 2. Create a Google Cloud Storage Bucket (for SQLite persistence)

Since SQLite requires a persistent file, we'll use Cloud Storage:

```bash
# Create a bucket (replace YOUR_BUCKET_NAME with a unique name)
gsutil mb -l europe-west1 gs://YOUR_BUCKET_NAME-event-db

# Or use the gcloud command
gcloud storage buckets create gs://YOUR_BUCKET_NAME-event-db --location=europe-west1
```

### 3. Deploy to Cloud Run

**Option A: Deploy with automatic build (recommended)**

```bash
gcloud run deploy event-scheduling-api \
  --source . \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --max-instances 1 \
  --min-instances 0 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --set-env-vars DB_PATH=/mnt/data/database.db \
  --execution-environment gen2
```

**Important Notes:**
- `--max-instances 1`: Required for SQLite (no concurrent writes)
- `--allow-unauthenticated`: Makes API publicly accessible
- `--region europe-west1`: Choose closest region to your users
- `--execution-environment gen2`: Required for better performance

**Option B: Build and deploy separately**

```bash
# Build the container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/event-scheduling-api

# Deploy the container
gcloud run deploy event-scheduling-api \
  --image gcr.io/YOUR_PROJECT_ID/event-scheduling-api \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --max-instances 1 \
  --min-instances 0 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --set-env-vars DB_PATH=/mnt/data/database.db \
  --execution-environment gen2
```

### 4. Get Your Service URL

After deployment, you'll see output like:

```
Service [event-scheduling-api] revision [event-scheduling-api-00001-abc] has been deployed and is serving 100 percent of traffic.
Service URL: https://event-scheduling-api-xxxxx-ew.a.run.app
```

**Save this URL** - you'll need it for your frontend configuration.

### 5. Test Your Deployment

```bash
# Test the health check
curl https://YOUR_SERVICE_URL/healthcheck

# Should return: "event-scheduling-api is up!"
```

## Important Limitations

### SQLite on Cloud Run

⚠️ **Current Setup Limitations:**
- SQLite on Cloud Run is **ephemeral** - data will be lost on restart
- `max-instances: 1` prevents horizontal scaling
- This is **fine for development/portfolio** but NOT for production

### Solutions for Production:

**Option 1: Cloud SQL PostgreSQL (Recommended for production)**
- Persistent, scalable, production-ready
- Requires code changes to use PostgreSQL instead of SQLite
- Costs ~$10-20/month

**Option 2: Cloud Storage FUSE (Experimental)**
- Mount Cloud Storage as a filesystem
- More complex setup
- Not officially recommended by Google

**For now, the ephemeral setup is good for:**
- Development
- Testing
- Portfolio/demo projects
- Low-traffic applications where data loss on redeploy is acceptable

## Frontend Configuration

After deploying, update your frontend environment variables:

**For local development** (`.env.local`):
```env
VITE_API_URL=https://YOUR_SERVICE_URL
```

**For production** (Netlify/Vercel/Firebase):
- Set environment variable: `VITE_API_URL` = `https://YOUR_SERVICE_URL`

## Updating Your Deployment

After making code changes:

```bash
# Simply redeploy (Cloud Run will rebuild)
gcloud run deploy event-scheduling-api \
  --source . \
  --region europe-west1
```

## Monitoring and Logs

```bash
# View logs
gcloud run services logs read event-scheduling-api --region europe-west1

# Follow logs in real-time
gcloud run services logs tail event-scheduling-api --region europe-west1

# View service details
gcloud run services describe event-scheduling-api --region europe-west1
```

## Cost Considerations

Cloud Run pricing (as of 2024):
- **Free tier**: 2 million requests/month
- **CPU**: ~$0.00002400/vCPU-second
- **Memory**: ~$0.00000250/GiB-second
- **Requests**: $0.40 per million requests

For a small app with `min-instances: 0`, you'll likely stay in the free tier.

## Troubleshooting

### WebSocket Connection Issues

If WebSocket connections fail, ensure your frontend uses:

```javascript
import io from 'socket.io-client';

const socket = io(API_URL, {
  transports: ['websocket', 'polling'],
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionAttempts: 5
});
```

### CORS Issues

The API allows all origins (`*`). For production, update in `main.py`:

```python
CORS(app, resources={r"/*": {"origins": "https://your-frontend-domain.com"}})
socketio = SocketIO(app, cors_allowed_origins="https://your-frontend-domain.com")
```

### Database Path Issues

The database path is set via `DB_PATH` environment variable. Current setup:
- Default: `database.db` (in container, ephemeral)
- Can be changed via: `--set-env-vars DB_PATH=/custom/path/database.db`

## Security Checklist

- [ ] Update CORS to specific origins in production
- [ ] Add rate limiting for API endpoints
- [ ] Implement authentication for sensitive operations
- [ ] Use HTTPS only (Cloud Run provides this by default)
- [ ] Review and limit `--allow-unauthenticated` if needed
- [ ] Monitor logs for suspicious activity

## Next Steps for Production

1. **Migrate to PostgreSQL**:
   - Use Cloud SQL PostgreSQL
   - Update code to use SQLAlchemy
   - Remove `max-instances: 1` limit

2. **Add Authentication**:
   - Implement JWT tokens
   - Add Firebase Auth or Auth0

3. **Add Monitoring**:
   - Set up Google Cloud Monitoring
   - Add error tracking (Sentry, etc.)

4. **Implement Caching**:
   - Use Cloud Memorystore (Redis)
   - Cache frequently accessed data

## Support

If you encounter issues:
1. Check logs: `gcloud run services logs tail event-scheduling-api --region europe-west1`
2. Verify service status: `gcloud run services describe event-scheduling-api --region europe-west1`
3. Test locally first with Docker
