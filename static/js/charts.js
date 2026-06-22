/** 交易复盘系统 - 图表模块 */

let currentAccount = '';

function switchAccount(account) {
    currentAccount = account;
    loadOverview();
    loadEquityCurve();
    loadSymbolAnalysis();
    loadTypeAnalysis();
    loadReviewInsights();
    loadTheoryDistribution();
    loadComparison();
}

let equityChartInstance = null;
let monthlyChartInstance = null;
let symbolChartInstance = null;
let typeChartInstance = null;
let qualityChartInstance = null;
let theoryChartInstance = null;

// 默认颜色
const COLORS = {
    profit: 'rgba(34, 197, 94, 1)',
    profitBg: 'rgba(34, 197, 94, 0.1)',
    loss: 'rgba(239, 68, 68, 1)',
    lossBg: 'rgba(239, 68, 68, 0.1)',
    grid: 'rgba(0,0,0,0.06)',
    buy: 'rgba(59, 130, 246, 1)',
    sell: 'rgba(239, 68, 68, 1)',
};

// ========== 加载概览 ==========
async function loadOverview() {
    try {
        let url = '/analysis/api/overview';
        if (currentAccount) url += '?account=' + currentAccount;
        const res = await fetch(url);
        const data = await res.json();
        const container = document.getElementById('overview-stats');
        container.innerHTML = `
            <div class="stat-card"><div class="stat-icon">📋</div><div class="stat-body">
                <div class="stat-value">${data.closed_trades}</div><div class="stat-label">已平仓交易</div>
            </div></div>
            <div class="stat-card"><div class="stat-icon">🎯</div><div class="stat-body">
                <div class="stat-value">${data.win_rate}%</div><div class="stat-label">胜率</div>
                <div class="stat-sub">${data.wins}胜 / ${data.losses}负</div>
            </div></div>
            <div class="stat-card ${data.total_pnl >= 0 ? 'profit' : 'loss'}"><div class="stat-icon">💰</div><div class="stat-body">
                <div class="stat-value">${data.total_pnl.toFixed(2)}</div><div class="stat-label">总盈亏</div>
            </div></div>
            <div class="stat-card"><div class="stat-icon">📊</div><div class="stat-body">
                <div class="stat-value">${data.profit_factor}</div><div class="stat-label">盈亏比</div>
                <div class="stat-sub">均盈 ${data.avg_win} / 均亏 ${data.avg_loss}</div>
            </div></div>
            <div class="stat-card"><div class="stat-icon">📉</div><div class="stat-body">
                <div class="stat-value">${data.max_drawdown_pct}%</div><div class="stat-label">最大回撤</div>
                <div class="stat-sub">$${data.max_drawdown.toFixed(2)}</div>
            </div></div>
            <div class="stat-card"><div class="stat-icon">✅</div><div class="stat-body">
                <div class="stat-value">${data.review_rate}%</div><div class="stat-label">复盘率</div>
                <div class="stat-sub">${data.review_count} 单已复盘</div>
            </div></div>
        `;
    } catch (e) {
        console.error('Failed to load overview:', e);
    }
}

// ========== 资金曲线 ==========
async function loadEquityCurve() {
    try {
        let url = '/analysis/api/equity_curve';
        if (currentAccount) url += '?account=' + currentAccount;
        const res = await fetch(url);
        const data = await res.json();
        renderEquityChart(data.equity_curve);
        renderMonthlyChart(data.monthly);
    } catch (e) {
        console.error('Failed to load equity curve:', e);
    }
}

function renderEquityChart(equityData) {
    const ctx = document.getElementById('equityChart').getContext('2d');
    if (equityChartInstance) equityChartInstance.destroy();

    if (!equityData || equityData.length === 0) {
        ctx.canvas.parentElement.innerHTML = '<p class="empty-state">暂无数据</p>';
        return;
    }

    const labels = equityData.map(d => d.date);
    const balances = equityData.map(d => d.balance);

    equityChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: '账户余额',
                data: balances,
                borderColor: '#22c55e',
                backgroundColor: (ctx) => {
                    const gradient = ctx.chart.ctx.createLinearGradient(0, 0, 0, 400);
                    gradient.addColorStop(0, 'rgba(34, 197, 94, 0.3)');
                    gradient.addColorStop(1, 'rgba(34, 197, 94, 0.0)');
                    return gradient;
                },
                fill: true,
                tension: 0.3,
                pointRadius: 3,
                pointHoverRadius: 6,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => `余额: $${ctx.parsed.y.toFixed(2)}`
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxTicksLimit: 10, font: { size: 11 } }
                },
                y: {
                    grid: { color: COLORS.grid },
                    ticks: {
                        callback: v => '$' + v.toFixed(0)
                    }
                }
            }
        }
    });
}

function renderMonthlyChart(monthlyData) {
    const ctx = document.getElementById('monthlyChart').getContext('2d');
    if (monthlyChartInstance) monthlyChartInstance.destroy();

    if (!monthlyData || monthlyData.length === 0) {
        ctx.canvas.parentElement.innerHTML = '<p class="empty-state">暂无月度数据</p>';
        return;
    }

    const labels = monthlyData.map(d => d.month);
    const pnls = monthlyData.map(d => d.pnl);
    const colors = pnls.map(v => v >= 0 ? COLORS.profit : COLORS.loss);

    monthlyChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: '月度盈亏',
                data: pnls,
                backgroundColor: colors,
                borderColor: colors,
                borderWidth: 1,
                borderRadius: 3,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const m = monthlyData[ctx.dataIndex];
                            return [`盈亏: $${m.pnl.toFixed(2)}`, `交易: ${m.trades}笔`, `胜率: ${m.win_rate}%`];
                        }
                    }
                }
            },
            scales: {
                x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                y: {
                    grid: { color: COLORS.grid },
                    ticks: { callback: v => '$' + v }
                }
            }
        }
    });
}

// ========== 品种分析 ==========
async function loadSymbolAnalysis() {
    try {
        let url = '/analysis/api/by_symbol';
        if (currentAccount) url += '?account=' + currentAccount;
        const res = await fetch(url);
        const data = await res.json();
        renderSymbolChart(data);
    } catch (e) {
        console.error('Failed to load symbol analysis:', e);
    }
}

function renderSymbolChart(symbolData) {
    const ctx = document.getElementById('symbolChart').getContext('2d');
    if (symbolChartInstance) symbolChartInstance.destroy();

    if (!symbolData || symbolData.length === 0) {
        ctx.canvas.parentElement.innerHTML = '<p class="empty-state">暂无品种数据</p>';
        return;
    }

    const top = symbolData.slice(0, 10);
    const labels = top.map(d => d.symbol);
    const pnls = top.map(d => d.pnl);
    const colors = pnls.map(v => v >= 0 ? COLORS.profit : COLORS.loss);

    symbolChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: '盈亏',
                data: pnls,
                backgroundColor: colors,
                borderColor: colors,
                borderRadius: 3,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const d = top[ctx.dataIndex];
                            return [`盈亏: $${d.pnl.toFixed(2)}`, `交易: ${d.trades}笔`, `胜率: ${d.win_rate}%`];
                        }
                    }
                }
            },
            scales: {
                x: { grid: { color: COLORS.grid }, ticks: { callback: v => '$' + v } },
                y: { grid: { display: false } }
            }
        }
    });
}

// ========== 方向分析 ==========
async function loadTypeAnalysis() {
    try {
        let url = '/analysis/api/by_type';
        if (currentAccount) url += '?account=' + currentAccount;
        const res = await fetch(url);
        const data = await res.json();
        renderTypeChart(data);
    } catch (e) {
        console.error('Failed to load type analysis:', e);
    }
}

function renderTypeChart(typeData) {
    const ctx = document.getElementById('typeChart').getContext('2d');
    if (typeChartInstance) typeChartInstance.destroy();

    if (!typeData || typeData.length === 0) {
        ctx.canvas.parentElement.innerHTML += '<p class="empty-state">暂无数据</p>';
        return;
    }

    const labels = typeData.map(d => d.type === 'buy' ? '做多 (Buy)' : '做空 (Sell)');
    const wins = typeData.map(d => d.wins);
    const losses = typeData.map(d => d.losses);

    typeChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { label: '盈利', data: wins, backgroundColor: COLORS.profit, borderRadius: 3 },
                { label: '亏损', data: losses, backgroundColor: COLORS.loss, borderRadius: 3 },
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'top' },
            },
            scales: {
                x: { grid: { display: false } },
                y: { grid: { color: COLORS.grid }, beginAtZero: true }
            }
        }
    });
}

// ========== 复盘洞察 ==========
async function loadReviewInsights() {
    try {
        let url = '/analysis/api/review_summary';
        if (currentAccount) url += '?account=' + currentAccount;
        const res = await fetch(url);
        const data = await res.json();
        renderReviewInsights(data);
    } catch (e) {
        console.error('Failed to load review insights:', e);
    }
}

function renderReviewInsights(data) {
    if (!data || data.total_reviews === 0) {
        document.getElementById('review-insights').innerHTML =
            '<p class="empty-state">暂无复盘数据，完成一些复盘后再来看洞察</p>';
        return;
    }

    // 摘要卡片
    const insightContainer = document.getElementById('review-insights');

    // 高频标签
    let tagsHtml = '';
    if (data.top_tags && data.top_tags.length > 0) {
        tagsHtml = data.top_tags.slice(0, 8).map(t =>
            `<span class="tag tag-default">${t.name} (${t.count})</span>`
        ).join(' ');
    }

    insightContainer.innerHTML = `
        <div class="insight-card">
            <h4>🏷️ 高频标签</h4>
            <div>${tagsHtml || '暂无标签'}</div>
        </div>
        <div class="insight-card">
            <h4>📈 趋势状态分布</h4>
            <div class="mini-chart" id="trend-dist">${renderSimpleList(data.trend_distribution)}</div>
        </div>
        <div class="insight-card">
            <h4>😊 情绪分布</h4>
            <div class="mini-chart" id="emotion-dist">${renderSimpleList(data.emotion_distribution)}</div>
        </div>
        <div class="insight-card">
            <h4>📊 入场质量分布</h4>
            <div id="quality-dist">${renderSimpleList(data.quality_distribution)}</div>
        </div>
    `;

    // 入场质量图表
    if (data.quality_distribution && data.quality_distribution.length > 0) {
        renderMiniBarChart('quality-dist', data.quality_distribution);
    }
}

function renderSimpleList(dist) {
    if (!dist || dist.length === 0) return '<span class="dim">暂无数据</span>';
    return dist.map(d =>
        `<div class="bar-item"><span class="bar-label">${d.name}</span><span class="bar-count">${d.count}</span></div>`
    ).join('');
}

function renderMiniBarChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const maxCount = Math.max(...data.map(d => d.count), 1);
    container.innerHTML = data.map(d =>
        `<div class="bar-item">
            <span class="bar-label">${d.name}</span>
            <div class="bar-track"><div class="bar-fill" style="width:${(d.count / maxCount * 100).toFixed(0)}%"></div></div>
            <span class="bar-count">${d.count}</span>
        </div>`
    ).join('');
}

// ========== 交易理论分布 ==========
async function loadTheoryDistribution() {
    try {
        const res = await fetch('/analysis/api/review_summary');
        const data = await res.json();
        renderTheoryChart(data.top_theories);
    } catch (e) {
        console.error('Failed to load theory distribution:', e);
    }
}

function renderTheoryChart(theories) {
    const ctx = document.getElementById('theoryChart').getContext('2d');
    if (theoryChartInstance) theoryChartInstance.destroy();

    if (!theories || theories.length === 0) {
        ctx.canvas.parentElement.innerHTML = '<p class="empty-state">暂无数据</p>';
        return;
    }

    const top = theories.slice(0, 8);
    const labels = top.map(t => t.name);
    const counts = top.map(t => t.count);

    theoryChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data: counts,
                backgroundColor: [
                    '#3b82f6', '#ef4444', '#22c55e', '#f59e0b',
                    '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'
                ],
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'right', labels: { font: { size: 11 } } }
            }
        }
    });
}

// ========== 复盘效果对比 ==========
async function loadComparison() {
    try {
        let url = '/analysis/api/review_insights';
        if (currentAccount) url += '?account=' + currentAccount;
        const res = await fetch(url);
        const data = await res.json();
        const panel = document.getElementById('comparison-panel');
        panel.innerHTML = `
            <div class="compare-grid">
                <div class="compare-card">
                    <h4>✅ 有复盘</h4>
                    <div class="compare-stat">${data.reviewed.count} 笔</div>
                    <div class="compare-pnl ${data.reviewed.pnl >= 0 ? 'profit' : 'loss'}">
                        总盈亏: $${data.reviewed.pnl.toFixed(2)}
                    </div>
                    <div class="compare-detail">胜率: ${data.reviewed.win_rate}%</div>
                    <div class="compare-detail">平均盈亏: $${data.reviewed.avg_pnl.toFixed(2)}</div>
                </div>
                <div class="compare-card">
                    <h4>❌ 未复盘</h4>
                    <div class="compare-stat">${data.unreviewed.count} 笔</div>
                    <div class="compare-pnl ${data.unreviewed.pnl >= 0 ? 'profit' : 'loss'}">
                        总盈亏: $${data.unreviewed.pnl.toFixed(2)}
                    </div>
                    <div class="compare-detail">胜率: ${data.unreviewed.win_rate}%</div>
                    <div class="compare-detail">平均盈亏: $${data.unreviewed.avg_pnl.toFixed(2)}</div>
                </div>
            </div>
        `;
    } catch (e) {
        console.error('Failed to load comparison:', e);
    }
}

// ========== 切换资金曲线视图 ==========
function switchEquityChart(view) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    // 重新加载，API 暂只返回全部，切换仅作 UI 演示
}

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    loadOverview();
    loadEquityCurve();
    loadSymbolAnalysis();
    loadTypeAnalysis();
    loadReviewInsights();
    loadTheoryDistribution();
    loadComparison();
});
