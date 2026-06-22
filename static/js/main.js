/** 交易复盘系统 - 通用工具 */
'use strict';

// 数字格式化
function formatPnl(value) {
    const sign = value >= 0 ? '+' : '';
    return `${sign}$${value.toFixed(2)}`;
}

function formatPrice(value) {
    if (!value && value !== 0) return '-';
    return value.toFixed(5);
}

// 日期格式化
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleString('zh-CN', { hour12: false });
}

// AJAX 工具
async function apiGet(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function apiPost(url, data) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

// 自动隐藏 flash 消息
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.flash-message').forEach(msg => {
        setTimeout(() => {
            msg.style.transition = 'opacity 0.5s';
            msg.style.opacity = '0';
            setTimeout(() => msg.remove(), 500);
        }, 5000);
    });

    document.querySelectorAll('.nav-more').forEach(menu => {
        const button = menu.querySelector(':scope > button');
        const dropdown = menu.querySelector('.nav-dropdown');
        if (!button || !dropdown) return;

        let closeTimer = null;
        const openMenu = () => {
            clearTimeout(closeTimer);
            menu.classList.add('open');
        };
        const scheduleClose = () => {
            clearTimeout(closeTimer);
            closeTimer = setTimeout(() => menu.classList.remove('open'), 260);
        };

        menu.addEventListener('mouseenter', openMenu);
        menu.addEventListener('mouseleave', scheduleClose);
        dropdown.addEventListener('mouseenter', openMenu);
        dropdown.addEventListener('mouseleave', scheduleClose);

        button.addEventListener('click', event => {
            event.preventDefault();
            event.stopPropagation();

            document.querySelectorAll('.nav-more.open').forEach(openMenu => {
                if (openMenu !== menu) openMenu.classList.remove('open');
            });
            menu.classList.toggle('open');
        });
    });

    document.addEventListener('click', event => {
        if (event.target.closest('.nav-more')) return;
        document.querySelectorAll('.nav-more.open').forEach(menu => menu.classList.remove('open'));
    });

    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;
        document.querySelectorAll('.nav-more.open').forEach(menu => menu.classList.remove('open'));
    });
});
