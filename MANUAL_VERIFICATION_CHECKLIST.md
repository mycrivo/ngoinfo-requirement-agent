# Admin Analytics - Manual Verification Checklist

This checklist should be completed before merging the Admin Analytics (Pipeline + Security) implementation.

## Prerequisites

- [ ] Application is running with admin credentials configured
- [ ] Database migrations have been applied (security_events table exists)
- [ ] `ADMIN_ANALYTICS_ENABLED=true` in environment configuration

## 1. Authentication & Access Control

- [ ] **Login as admin** → Navigate to `/admin/analytics`
- [ ] **Verify admin-only access** → Non-admin users should be redirected/blocked
- [ ] **Check RBAC enforcement** → All API endpoints require admin role
- [ ] **Session management** → Logout/login cycle works correctly

## 2. Dashboard Loading & UI

- [ ] **Analytics dashboard loads** → `/admin/analytics` displays without errors
- [ ] **No external CDN dependencies** → Inspect network tab, all assets served locally
- [ ] **CSP compliance** → No CSP violations in browser console
- [ ] **Self-hosted Chart.js** → Verify `static/js/chart.min.js` loads correctly
- [ ] **Tab navigation** → Pipeline and Security tabs switch correctly
- [ ] **Date range controls** → Start/end date inputs are functional

## 3. Pipeline Analytics

- [ ] **KPI cards populate** → Numbers appear for 30-day default window
  - [ ] Total Ingested count displays
  - [ ] QA Approved count displays
  - [ ] Published count displays  
  - [ ] Templates Generated count displays
- [ ] **Pipeline trends chart** → Line chart renders with data points
- [ ] **Source breakdown chart** → Doughnut chart shows data distribution
- [ ] **Date filtering** → Changing dates updates all pipeline metrics

## 4. Security Analytics

- [ ] **Security KPIs populate** → Security tab shows meaningful numbers
  - [ ] Login Success count displays
  - [ ] Login Failures count displays
  - [ ] Rate Limit Hits count displays
  - [ ] Forbidden Access count displays
- [ ] **Security trends chart** → Login success/failure trends over time
- [ ] **IP breakdown table** → Shows hashed IP addresses with event counts
- [ ] **User breakdown table** → Shows users with security events (if any)
- [ ] **No raw PII displayed** → IPs are hashed, no sensitive data exposed

## 5. CSV Export Functionality

- [ ] **Pipeline CSV export** → Download works and contains correct columns
  - [ ] File downloads with proper naming convention
  - [ ] Contains: Metric, Value, Period columns
  - [ ] No PII beyond role/timestamp
  - [ ] Data matches dashboard display
- [ ] **Security CSV export** → Download works with anonymized data
  - [ ] IP addresses are hashed (max 8 chars + ...)
  - [ ] No raw IP addresses or sensitive data
  - [ ] Event counts and types are correct
- [ ] **Date range filtering** → CSV exports respect selected date ranges

## 6. Feature Flag Testing

- [ ] **Feature flag ON** → `ADMIN_ANALYTICS_ENABLED=true` allows access
- [ ] **Feature flag OFF** → Set `ADMIN_ANALYTICS_ENABLED=false`
  - [ ] `/admin/analytics` returns 404
  - [ ] All API endpoints return 404
  - [ ] Health endpoint returns 404
- [ ] **Restore feature flag** → Set back to `true` for remaining tests

## 7. API Health & Performance

- [ ] **Health endpoint** → `GET /admin/api/analytics/health` returns 200 OK
  - [ ] Response includes `{"ok": true, "features": ["pipeline", "security"]}`
  - [ ] Timestamp is current
  - [ ] Cache status is reported correctly
- [ ] **Response times** → All API calls complete in < 500ms (with cache warmed)
- [ ] **Cache behavior** → Second identical request is faster (if not in test mode)

## 8. Error Handling & Logging

- [ ] **No JavaScript errors** → Browser console is clean
- [ ] **Graceful error handling** → Invalid date ranges show user-friendly errors
- [ ] **Structured logging** → Check application logs for analytics access events
- [ ] **No exceptions in logs** → No Python stack traces during normal usage

## 9. Security Verification

- [ ] **IP anonymization** → Database contains only hashed IPs, never raw
- [ ] **Input validation** → Invalid query parameters are rejected
- [ ] **SQL injection protection** → Special characters in inputs don't cause errors
- [ ] **XSS prevention** → User input is properly escaped in displays

## 10. Data Accuracy

- [ ] **KPI calculations** → Spot-check numbers against database queries
- [ ] **Date range filtering** → Verify data changes when dates are modified
- [ ] **Trend calculations** → Charts show logical progressions over time
- [ ] **Source breakdown** → Provider/domain distributions make sense

## 11. Browser Compatibility

- [ ] **Chrome/Chromium** → Full functionality works
- [ ] **Firefox** → Charts render and interactions work
- [ ] **Safari** → (if available) Basic functionality verified
- [ ] **Mobile responsive** → Dashboard is usable on smaller screens

## 12. Final Validation

- [ ] **Clean browser console** → No errors, warnings, or CSP violations
- [ ] **All charts interactive** → Hover effects and animations work
- [ ] **Export naming** → CSV files have descriptive, dated filenames
- [ ] **Performance acceptable** → Page loads and interactions feel responsive
- [ ] **Documentation updated** → README runbook section is accurate

## Post-Verification Notes

**Date Tested:** _______________

**Tester:** _______________

**Environment:** _______________

**Issues Found:** 
_List any issues discovered during testing_

**Resolution Status:**
_Note if issues were resolved or require follow-up_

---

**✅ All items checked = Ready for merge**

**❌ Any items failing = Requires fixes before merge**
