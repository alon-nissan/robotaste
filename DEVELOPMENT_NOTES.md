# 🔧 Development Branch - Future Improvements

This branch is for active development and new features. The `main` branch contains the stable v1.0-demo version.

## 🚧 **Planned Improvements**

### **High Priority**
- [ ] Add PostgreSQL support for production deployment
- [ ] Implement user authentication and session security
- [ ] Add real-time websocket updates to replace manual refresh
- [ ] Enhanced analytics dashboard with visualization charts
- [ ] Mobile-optimized interface improvements

### **Medium Priority**  
- [ ] Add more ingredient types and concentration ranges
- [ ] Implement advanced questionnaire logic (branching, conditional)
- [ ] Add data backup and recovery systems
- [ ] Create admin panel for session management
- [ ] Add experiment templates and presets

### **Low Priority**
- [ ] Clean up unused column variables flagged by linter
- [ ] Add comprehensive unit tests
- [ ] Performance optimization for large datasets
- [ ] Add multi-language support
- [ ] Create API endpoints for external integration

## 🔄 **Development Workflow**

1. **Feature Branches**: Create from `development`
   ```bash
   git checkout development
   git checkout -b feature/your-feature-name
   ```

2. **Testing**: Always test locally before committing
   ```bash
   streamlit run main_app.py
   ```

3. **Merge Back**: Pull request to `development` branch
4. **Stable Release**: Merge `development` → `main` when ready

## ⚠️ **Known Issues to Address**

### **Current Technical Debt**
- Unused column variables (col1, col3) in multiple functions
- Some auto-refresh logic still present (commented out)
- SQLite limitations for concurrent users
- Manual refresh requirement for real-time updates

### **Enhancement Opportunities**
- Better error handling for network issues
- More sophisticated concentration mapping algorithms
- Advanced data visualization tools
- Improved mobile responsiveness

## 🧪 **Testing Guidelines**

### **Before Any Commit**
1. Test both moderator and subject interfaces
2. Verify multi-device session management
3. Check that no blank screens occur
4. Ensure all interactive elements have unique keys
5. Test with multiple concurrent sessions

### **Release Testing**
1. Full end-to-end experiment workflow
2. Data export functionality
3. QR code generation and scanning
4. Cross-browser compatibility
5. Mobile device testing

---

*This development branch maintains the stable demo functionality while allowing for safe experimentation and improvements.*