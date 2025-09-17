# 🚀 RoboTaste Multi-Device Deployment Guide

## Overview

This guide covers deploying the RoboTaste multi-device taste preference experiment platform on Streamlit Cloud with real-time synchronization between moderator and subject devices.

## 📋 Prerequisites

- GitHub account
- Streamlit Cloud account (free at https://share.streamlit.io/)
- Git repository with your RoboTaste code

## 🏗️ Architecture

The application uses a **session-based multi-device architecture**:

- **Moderator Device**: Desktop/laptop with full dashboard (creates sessions)
- **Subject Device**: Any device (phone, tablet, laptop) - joins sessions via code/QR
- **Real-time Sync**: 5-second polling with SQLite database persistence
- **Session Management**: Unique 6-character codes for device pairing

## 📁 File Structure

Ensure your repository has these files:

```
RoboTaste/
├── main_app.py                 # Main Streamlit application
├── session_manager.py          # Session management & QR codes  
├── callback.py                 # Experiment logic & vertical sliders
├── sql_handler.py             # Database operations
├── requirements.txt            # Dependencies
├── .streamlit/
│   └── config.toml            # Streamlit configuration
└── DEPLOYMENT_GUIDE.md        # This guide
```

## 📦 Dependencies (requirements.txt)

```txt
streamlit>=1.49.1
pandas>=1.5.3
plotly>=5.17.0
streamlit-drawable-canvas>=0.9.3
streamlit-vertical-slider>=2.5.5
streamlit-toggle>=0.1.3
streamlit-space>=0.1.5
qrcode>=7.4.2
pillow>=9.5.0
```

## 🚀 Streamlit Cloud Deployment

### Step 1: Prepare Repository

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Deploy RoboTaste multi-device version"
   git push origin main
   ```

### Step 2: Deploy on Streamlit Cloud

1. **Visit** https://share.streamlit.io/
2. **Sign in** with GitHub
3. **Click "New app"**
4. **Configure**:
   - Repository: `your-username/RoboTaste`
   - Branch: `main`
   - Main file path: `main_app.py`
   - App URL: Choose custom URL like `robotaste-experiment`

### Step 3: Configure Settings

In Streamlit Cloud dashboard:
- **Secrets**: Not needed (using local SQLite)
- **Python version**: 3.11 (recommended)
- **Advanced settings**: Use defaults

## 🔗 URL Structure

Once deployed, your app will be available at:
`https://your-app-name.streamlit.app/`

### Multi-Device URLs:
- **Landing Page**: `https://your-app.streamlit.app/`
- **Moderator**: `https://your-app.streamlit.app/?role=moderator&session=ABC123`
- **Subject**: `https://your-app.streamlit.app/?role=subject&session=ABC123`

## 📱 Usage Workflow

### For Researchers (Moderator):

1. **Navigate** to your deployed app
2. **Click "🎮 New Session"**
3. **Enter moderator name** 
4. **Share session code** or QR code with subjects
5. **Monitor** real-time subject responses
6. **Configure experiments** and view analytics

### For Participants (Subjects):

1. **Receive session code** from researcher
2. **Visit app** and click "📱 Join Session"  
3. **Enter 6-digit code** or scan QR code
4. **Complete experiment** on any device
5. **Interface optimized** for mobile/tablet use

## 🔄 Real-Time Synchronization

- **Auto-refresh**: Every 5 seconds
- **Session persistence**: 24-hour cleanup
- **Connection status**: Visual indicators
- **Data sync**: Immediate for critical events

## 📊 Data Management

### Database:
- **SQLite file** (persistent on Streamlit Cloud)
- **Automatic migrations** for schema updates
- **Session table** for device pairing
- **Responses table** for experiment data

### Export Options:
- **CSV downloads** available in moderator interface
- **Real-time analytics** with plotly charts
- **JSON data** for concentration details

## 🎨 Features Included

### Multi-Device Architecture:
- ✅ Session-based device pairing
- ✅ QR code generation for easy joining
- ✅ Real-time connection status
- ✅ Auto-refresh mechanisms

### Experiment Interfaces:
- ✅ **2D Grid**: Binary mixture coordinate selection
- ✅ **Vertical Sliders**: Multi-component concentration control
- ✅ **Questionnaires**: Pre/post experiment surveys
- ✅ **Mobile Optimized**: Responsive design

### Moderator Dashboard:
- ✅ **Live Monitoring**: Real-time subject tracking
- ✅ **Session Management**: Create/monitor sessions
- ✅ **Analytics**: Response patterns & statistics  
- ✅ **Data Export**: CSV downloads

## 🔧 Troubleshooting

### Common Issues:

**"Session not found"**
- Ensure 6-character code is correct
- Check session hasn't expired (24h limit)
- Try creating new session

**"Device not connecting"**
- Check internet connection
- Clear browser cache
- Try incognito/private browsing

**"Sliders not working"**
- Ensure streamlit-vertical-slider installed
- Check browser compatibility
- Try desktop browser if mobile issues

**"App won't deploy"**
- Verify all files committed to GitHub
- Check requirements.txt syntax
- Review Streamlit Cloud logs

### Performance Tips:
- **Mobile Subjects**: Use latest browser versions
- **Large Studies**: Consider connection limits
- **Data Export**: Regular CSV downloads recommended

## 📈 Scaling Considerations

### Concurrent Users:
- **Streamlit Cloud Free**: ~10-20 concurrent users
- **For larger studies**: Consider upgrading plan

### Database:
- **SQLite**: Suitable for moderate concurrent use
- **For heavy load**: Consider PostgreSQL migration

## 🔒 Security Notes

- **Session codes**: 6-character random generation
- **No authentication**: Consider adding for sensitive studies
- **Data privacy**: Local database, no external services
- **SSL**: Automatic with Streamlit Cloud (.streamlit.app domain)

## 🎯 Testing Multi-Device Locally

Before deployment, test locally:

```bash
# Terminal 1 - Start app
streamlit run main_app.py

# Terminal 2 - Test session creation
curl http://localhost:8501

# Use multiple browser windows/devices to simulate:
# - Moderator: Create session
# - Subject: Join with code
```

## 📞 Support

For deployment issues:
- **Streamlit Community**: https://discuss.streamlit.io/
- **GitHub Issues**: Create issues in your repository
- **Streamlit Docs**: https://docs.streamlit.io/streamlit-cloud

---

## 🎉 Ready to Deploy!

Your RoboTaste multi-device experiment platform is now ready for deployment on Streamlit Cloud with:

- ✅ **Session-based multi-device architecture**
- ✅ **Real-time synchronization**
- ✅ **QR code device pairing**
- ✅ **Vertical slider interfaces**
- ✅ **Mobile-optimized subject interface**
- ✅ **Comprehensive moderator dashboard**
- ✅ **Cloud-ready configuration**

Follow the steps above to deploy and start conducting multi-device taste preference experiments!