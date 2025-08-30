/**
 * Analytics.js - Lightweight wrapper for Chart.js analytics
 * Self-hosted, no external CDNs
 */

class AnalyticsDashboard {
    constructor() {
        this.charts = {};
        this.currentTab = 'pipeline';
        this.dateRange = {
            start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            end: new Date().toISOString().split('T')[0]
        };
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadData();
    }

    bindEvents() {
        // Tab switching
        document.querySelectorAll('[data-tab]').forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchTab(e.target.dataset.tab);
            });
        });

        // Date range changes
        document.getElementById('start-date')?.addEventListener('change', () => this.loadData());
        document.getElementById('end-date')?.addEventListener('change', () => this.loadData());

        // Export buttons
        document.querySelectorAll('[data-export]').forEach(btn => {
            btn.addEventListener('click', (e) => this.exportData(e.target.dataset.export));
        });
    }

    switchTab(tabName) {
        this.currentTab = tabName;
        
        // Update active tab
        document.querySelectorAll('[data-tab]').forEach(t => t.classList.remove('active'));
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        
        // Show/hide content
        document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
        document.querySelector(`#${tabName}-content`).style.display = 'block';
        
        // Load tab-specific data
        this.loadData();
    }

    async loadData() {
        try {
            this.showLoading();
            
            if (this.currentTab === 'pipeline') {
                await this.loadPipelineData();
            } else {
                await this.loadSecurityData();
            }
            
            this.hideLoading();
        } catch (error) {
            console.error('Error loading analytics data:', error);
            this.showError('Failed to load analytics data');
        }
    }

    async loadPipelineData() {
        const [kpis, trends, sources, qa] = await Promise.all([
            this.fetchData('/admin/api/analytics/pipeline/kpis'),
            this.fetchData('/admin/api/analytics/pipeline/trends'),
            this.fetchData('/admin/api/analytics/pipeline/sources'),
            this.fetchData('/admin/api/analytics/pipeline/qa')
        ]);

        this.updatePipelineKPIs(kpis);
        this.updatePipelineTrends(trends);
        this.updateSourceBreakdown(sources);
        this.updateQAMetrics(qa);
    }

    async loadSecurityData() {
        const [kpis, trends, breakdown] = await Promise.all([
            this.fetchData('/admin/api/analytics/security/kpis'),
            this.fetchData('/admin/api/analytics/security/trends'),
            this.fetchData('/admin/api/analytics/security/breakdown')
        ]);

        this.updateSecurityKPIs(kpis);
        this.updateSecurityTrends(trends);
        this.updateSecurityBreakdown(breakdown);
    }

    async fetchData(endpoint) {
        const params = new URLSearchParams({
            start: this.dateRange.start,
            end: this.dateRange.end
        });
        
        const response = await fetch(`${endpoint}?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    }

    updatePipelineKPIs(data) {
        const kpiElements = {
            'total-ingested': data.total_ingested || 0,
            'total-approved': data.total_qa_approved || 0,
            'total-published': data.total_published || 0,
            'total-templates': data.total_templates || 0
        };

        Object.entries(kpiElements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value.toLocaleString();
        });
    }

    updatePipelineTrends(data) {
        this.renderChart('pipeline-trends', {
            type: 'line',
            data: {
                labels: data.map(d => d.date),
                datasets: [{
                    label: 'Opportunities',
                    data: data.map(d => d.count),
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }

    updateSourceBreakdown(data) {
        this.renderChart('source-breakdown', {
            type: 'doughnut',
            data: {
                labels: data.map(d => d.source),
                datasets: [{
                    data: data.map(d => d.count),
                    backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }

    updateQAMetrics(data) {
        const qaElements = {
            'qa-approval-rate': `${((data.approval_rate || 0) * 100).toFixed(1)}%`,
            'qa-avg-review-time': `${(data.avg_review_time || 0).toFixed(1)}h`,
            'qa-total-reviews': data.total_reviews || 0
        };

        Object.entries(qaElements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        });
    }

    updateSecurityKPIs(data) {
        const securityElements = {
            'security-login-success': data.login_success || 0,
            'security-login-failure': data.login_failure || 0,
            'security-rate-limit': data.rate_limit || 0,
            'security-forbidden': data.forbidden || 0
        };

        Object.entries(securityElements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value.toLocaleString();
        });
    }

    updateSecurityTrends(data) {
        this.renderChart('security-trends', {
            type: 'line',
            data: {
                labels: data.map(d => d.date),
                datasets: [
                    {
                        label: 'Login Success',
                        data: data.filter(d => d.event_type === 'login_success').map(d => d.count),
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Login Failure',
                        data: data.filter(d => d.event_type === 'login_failure').map(d => d.count),
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' }
                },
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }

    updateSecurityBreakdown(data) {
        // Update IP breakdown table
        const ipTable = document.getElementById('ip-breakdown-table');
        if (ipTable && data.ip_breakdown) {
            ipTable.innerHTML = data.ip_breakdown.map(item => `
                <tr>
                    <td>${this.hashIP(item.ip_hashed)}</td>
                    <td>${item.count}</td>
                    <td>${item.event_types.join(', ')}</td>
                </tr>
            `).join('');
        }

        // Update user breakdown table
        const userTable = document.getElementById('user-breakdown-table');
        if (userTable && data.user_breakdown) {
            userTable.innerHTML = data.user_breakdown.map(item => `
                <tr>
                    <td>${item.user_email}</td>
                    <td>${item.count}</td>
                    <td>${item.event_types.join(', ')}</td>
                </tr>
            `).join('');
        }
    }

    renderChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // Destroy existing chart if it exists
        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
        }

        // Create new chart
        this.charts[canvasId] = new Chart(canvas, config);
    }

    hashIP(ipHash) {
        // Return first 8 characters for display (already hashed)
        return ipHash.substring(0, 8) + '...';
    }

    async exportData(type) {
        try {
            const params = new URLSearchParams({
                start: this.dateRange.start,
                end: this.dateRange.end,
                format: 'csv'
            });
            
            const response = await fetch(`/admin/api/analytics/${this.currentTab}/${type}?${params}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${this.currentTab}-${type}-${this.dateRange.start}-${this.dateRange.end}.csv`;
            a.click();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Export failed:', error);
            this.showError('Export failed');
        }
    }

    showLoading() {
        document.querySelectorAll('.loading').forEach(el => el.style.display = 'block');
    }

    hideLoading() {
        document.querySelectorAll('.loading').forEach(el => el.style.display = 'none');
    }

    showError(message) {
        // Simple error display
        const errorDiv = document.getElementById('error-message');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            setTimeout(() => errorDiv.style.display = 'none', 5000);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new AnalyticsDashboard();
});
