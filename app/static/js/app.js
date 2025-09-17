// app/static/js/app.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Chart.js
    initPriceChart();

    // Load initial data
    loadAccountInfo();
    loadPositions();
    loadOpenOrders();
    
    // Set up form handling
    const orderForm = document.getElementById('orderForm');
    const orderTypeSelect = document.getElementById('orderType');
    
    orderTypeSelect.addEventListener('change', togglePriceFields);
    togglePriceFields(); // Initial call
    
    orderForm.addEventListener('submit', function(e) {
        e.preventDefault();
        placeOrder();
    });
    
    // Set up WebSocket connection for real-time updates
    connectWebSocket();
});

// WebSocket management
let ws = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;
let priceChart = null;
const priceData = {
    labels: [],
    values: []
};

function initPriceChart() {
    const chartContainer = document.getElementById('priceChart').parentElement;
    // Limit chart container size via inline style (or use a CSS class)
    chartContainer.style.maxWidth = '400px';
    chartContainer.style.maxHeight = '250px';
    chartContainer.style.width = '100%';
    chartContainer.style.height = '250px';
    chartContainer.style.overflow = 'hidden';

    const ctx = document.getElementById('priceChart').getContext('2d');
    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: priceData.labels,
            datasets: [{
                label: 'Price (USDT)',
                data: priceData.values,
                borderColor: '#4F46E5',
                backgroundColor: 'rgba(79, 70, 229, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: 0
            },
            scales: {
                x: {
                    display: true,
                    title: { display: true, text: 'Time' },
                    ticks: { maxTicksLimit: 8 }
                },
                y: {
                    display: true,
                    title: { display: true, text: 'Price (USDT)' },
                    position: 'right'
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return `Price: $${context.parsed.y.toFixed(2)}`;
                        }
                    }
                }
            },
            interaction: { intersect: false, mode: 'index' }
        }
    });
}

function updatePriceChart(price, timestamp) {
    if (!priceChart) return;
    
    const time = new Date(timestamp).toLocaleTimeString();
    
    // Keep only the last 50 data points
    if (priceData.labels.length > 50) {
        priceData.labels.shift();
        priceData.values.shift();
    }
    
    priceData.labels.push(time);
    priceData.values.push(price);
    
    priceChart.update();
}

function connectWebSocket() {
    try {
        // Close existing connection if any
        if (ws) {
            ws.close();
        }
        
        // Connect to the main trade WebSocket
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/trade`;
        ws = new WebSocket(wsUrl);
        
        ws.onopen = function() {
            console.log('WebSocket connected');
            reconnectAttempts = 0;
            showAlert('Connected to real-time data stream', 'success');
            
            // Subscribe to desired streams
            subscribeToStreams();
        };
        
        ws.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        ws.onclose = function() {
            console.log('WebSocket disconnected');
            showAlert('Disconnected from real-time data', 'error');
            attemptReconnect();
        };
        
        ws.onerror = function(error) {
            console.error('WebSocket error:', error);
            showAlert('WebSocket connection error', 'error');
        };
        
    } catch (error) {
        console.error('Failed to connect WebSocket:', error);
        attemptReconnect();
    }
}

function subscribeToStreams() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        // The server now automatically starts user_data and mini_ticker streams
        // You can add additional subscriptions here if needed
        console.log('Connected to real-time trading data streams');
        
        // Example: Subscribe to specific symbol if user has entered one
        const symbol = document.getElementById('symbol').value;
        if (symbol) {
            ws.send(JSON.stringify({
                action: 'subscribe',
                type: 'ticker',
                symbol: symbol.toUpperCase()
            }));
        }
    }
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'mini_ticker':
            updateTickerDisplay(data);
            break;
        case 'user_data':
            handleUserDataUpdate(data);
            break;
        case 'ticker':
            updateSymbolTicker(data);
            break;
        case 'kline':
            updateChartData(data);
            break;
        case 'depth':
            updateOrderBook(data);
            break;
        case 'error':
            console.error('WebSocket error:', data.message);
            showAlert('WebSocket error: ' + data.message, 'error');
            break;
        case 'pong':
            // Heartbeat response
            break;
        case 'connection':
            console.log('WebSocket connection status:', data.status);
            if (data.status === 'connected') {
                showAlert('Connected to real-time trading data', 'success');
            }
            break;
        default:
            console.log('Unknown WebSocket message type:', data.type);
    }
}

function updateTickerDisplay(tickerData) {
    // Update the price chart with the latest price
    updatePriceChart(tickerData.price, tickerData.timestamp);
    
    // You can also update a ticker display or other UI elements
    // For example, show the latest price for the current symbol
    const currentSymbol = document.getElementById('symbol').value;
    if (currentSymbol && tickerData.symbol === currentSymbol.toUpperCase()) {
        // Update UI with current symbol price
        const priceElement = document.getElementById('currentPrice');
        if (priceElement) {
            priceElement.textContent = `Current Price: $${tickerData.price.toFixed(2)}`;
        }
    }
}

function handleUserDataUpdate(userData) {
    // Handle account and order updates
    if (userData.event_type === 'ACCOUNT_UPDATE') {
        loadAccountInfo(); // Refresh account info
    } else if (userData.event_type === 'ORDER_TRADE_UPDATE') {
        loadOpenOrders(); // Refresh orders
        loadPositions(); // Refresh positions
        
        // Show notification for order updates
        const orderUpdate = userData.data.o;
        showAlert(`Order ${orderUpdate.s}: ${orderUpdate.X} - ${orderUpdate.N} ${orderUpdate.s} @ ${orderUpdate.p || 'market'}`, 'success');
    }
}

function attemptReconnect() {
    if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        const delay = Math.pow(2, reconnectAttempts) * 1000; // Exponential backoff
        console.log(`Attempting reconnect in ${delay}ms (attempt ${reconnectAttempts})`);
        setTimeout(connectWebSocket, delay);
    } else {
        console.error('Max reconnection attempts reached');
        showAlert('Failed to reconnect to real-time data. Please refresh the page.', 'error');
    }
}

// Keep connection alive with heartbeats
setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            action: 'ping',
            timestamp: Date.now()
        }));
    }
}, 30000); // Send ping every 30 seconds

// Existing functions (unchanged)
function togglePriceFields() {
    const orderType = document.getElementById('orderType').value;
    const priceField = document.getElementById('priceField');
    const stopPriceField = document.getElementById('stopPriceField');
    
    priceField.classList.add('hidden');
    stopPriceField.classList.add('hidden');
    
    if (orderType === 'LIMIT') {
        priceField.classList.remove('hidden');
    } else if (orderType === 'STOP_LIMIT') {
        priceField.classList.remove('hidden');
        stopPriceField.classList.remove('hidden');
    }
}

function showAlert(message, type = 'error') {
    const alertArea = document.getElementById('alertArea');
    alertArea.className = `mb-6 p-4 rounded-lg ${type === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`;
    alertArea.textContent = message;
    alertArea.classList.remove('hidden');
    setTimeout(() => alertArea.classList.add('hidden'), 5000);
}

async function placeOrder() {
    const symbol = document.getElementById('symbol').value;
    const side = document.getElementById('side').value;
    const orderType = document.getElementById('orderType').value;
    const quantity = document.getElementById('quantity').value;
    const price = document.getElementById('price').value;
    const stopPrice = document.getElementById('stopPrice').value;
    
    if (!symbol || !quantity) {
        showAlert('Symbol and Quantity are required.');
        return;
    }
    
    const orderData = {
        symbol,
        side,
        order_type: orderType,
        quantity: quantity ? parseFloat(quantity) : null,
        price: price ? parseFloat(price) : null,
        stop_price: stopPrice ? parseFloat(stopPrice) : null
    };
    
    try {
        const response = await fetch('/api/orders/place', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert('Order placed successfully!', 'success');
            loadOpenOrders();
        } else {
            showAlert('Error: ' + result.detail);
        }
    } catch (error) {
        showAlert('Error placing order: ' + error.message);
    }
}

async function cancelOrder(orderId, symbol) {
    try {
        const response = await fetch('/api/orders/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_id: orderId, symbol })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert('Order cancelled successfully!', 'success');
            loadOpenOrders();
        } else {
            showAlert('Error: ' + result.detail);
        }
    } catch (error) {
        showAlert('Error cancelling order: ' + error.message);
    }
}

async function loadAccountInfo() {
    const spinner = document.getElementById('accountSpinner');
    const accountInfoDiv = document.getElementById('accountInfo');
    
    spinner.classList.remove('hidden');
    try {
        const response = await fetch('/api/account/balance');
        const data = await response.json();
        
        if (response.ok) {
            accountInfoDiv.innerHTML = `
                <p class="text-sm"><strong>Balance:</strong> ${data.balance.totalWalletBalance || 'N/A'} USDT</p>
                <p class="text-sm"><strong>Equity:</strong> ${data.balance.totalMarginBalance || 'N/A'} USDT</p>
                <p class="text-sm"><strong>Unrealized P&L:</strong> ${data.balance.totalUnrealizedProfit || 'N/A'} USDT</p>
                <p class="text-sm"><strong>Available:</strong> ${data.balance.availableBalance || 'N/A'} USDT</p>
            `;
        } else {
            accountInfoDiv.innerHTML = '<p class="text-red-500 text-sm">Error loading account info</p>';
        }
    } catch (error) {
        accountInfoDiv.innerHTML = '<p class="text-red-500 text-sm">Error loading account info</p>';
    } finally {
        spinner.classList.add('hidden');
    }
}

async function loadPositions() {
    const spinner = document.getElementById('positionsSpinner');
    const positionsInfoDiv = document.getElementById('positionsInfo');
    
    spinner.classList.remove('hidden');
    try {
        const response = await fetch('/api/account/positions');
        const data = await response.json();
        
        if (response.ok && data.positions) {
            const openPositions = data.positions.filter(p => parseFloat(p.positionAmt) !== 0);
            
            if (openPositions.length > 0) {
                let html = '<div class="overflow-x-auto"><table class="min-w-full divide-y divide-gray-200"><thead class="bg-gray-50"><tr><th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Symbol</th><th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th><th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Entry Price</th><th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">P&L</th></tr></thead><tbody class="bg-white divide-y divide-gray-200">';
                
                openPositions.forEach(position => {
                    html += `<tr>
                        <td class="px-4 py-2 whitespace-nowrap text-sm">${position.symbol}</td>
                        <td class="px-4 py-2 whitespace-nowrap text-sm">${position.positionAmt}</td>
                        <td class="px-4 py-2 whitespace-nowrap text-sm">${position.entryPrice}</td>
                        <td class="px-4 py-2 whitespace-nowrap text-sm ${parseFloat(position.unRealizedProfit) >= 0 ? 'text-green-600' : 'text-red-600'}">${position.unRealizedProfit}</td>
                    </tr>`;
                });
                
                html += '</tbody></table></div>';
                positionsInfoDiv.innerHTML = html;
            } else {
                positionsInfoDiv.innerHTML = '<p class="text-gray-600 text-sm">No open positions</p>';
            }
        } else {
            positionsInfoDiv.innerHTML = '<p class="text-red-500 text-sm">Error loading positions</p>';
        }
    } catch (error) {
        positionsInfoDiv.innerHTML = '<p class="text-red-500 text-sm">Error loading positions</p>';
    } finally {
        spinner.classList.add('hidden');
    }
}

async function loadOpenOrders() {
    const spinner = document.getElementById('ordersSpinner');
    const ordersInfoDiv = document.getElementById('ordersInfo');
    
    spinner.classList.remove('hidden');
    try {
        const response = await fetch('/api/orders/open');
        const data = await response.json();
        
        if (response.ok && data.orders) {
            if (data.orders.length > 0) {
                let html = '<div class="overflow-x-auto"><table class="min-w-full divide-y divide-gray-200"><thead class="bg-gray-50"><tr><th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Symbol</th><th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Side</th><th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th><th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Quantity</th><th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Price</th><th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th><th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th></tr></thead><tbody class="bg-white divide-y divide-gray-200">';
                
                data.orders.forEach(order => {
                    html += `<tr>
                        <td class="px-4 py-2 whitespace-nowrap text-sm">${order.symbol}</td>
                        <td class="px-4 py-2 whitespace-nowrap text-sm">${order.side}</td>
                        <td class="px-4 py-2 whitespace-nowrap text-sm">${order.type}</td>
                        <td class="px-4 py-2 whitespace-nowrap text-sm">${order.origQty}</td>
                        <td class="px-4 py-2 whitespace-nowrap text-sm">${order.price || 'N/A'}</td>
                        <td class="px-4 py-2 whitespace-nowrap text-sm">${order.status}</td>
                        <td class="px-4 py-2 whitespace-nowrap text-sm">
                            <button onclick="cancelOrder('${order.orderId}', '${order.symbol}')" class="text-red-600 hover:text-red-800 text-xs">Cancel</button>
                        </td>
                    </tr>`;
                });
                
                html += '</tbody></table></div>';
                ordersInfoDiv.innerHTML = html;
            } else {
                ordersInfoDiv.innerHTML = '<p class="text-gray-600 text-sm">No open orders</p>';
            }
        } else {
            ordersInfoDiv.innerHTML = '<p class="text-red-500 text-sm">Error loading orders</p>';
        }
    } catch (error) {
        ordersInfoDiv.innerHTML = '<p class="text-red-500 text-sm">Error loading orders</p>';
    } finally {
        spinner.classList.add('hidden');
    }
}

// Additional helper functions for WebSocket data handling
function updateSymbolTicker(tickerData) {
    // Handle individual symbol ticker updates
    console.log('Symbol ticker update:', tickerData);
}

function updateChartData(klineData) {
    // Handle kline/candlestick data updates
    console.log('Kline update:', klineData);
}

function updateOrderBook(depthData) {
    // Handle order book depth updates
    console.log('Depth update:', depthData);
}

// Manual reconnect function for UI
function reconnectWebSocket() {
    reconnectAttempts = 0;
    connectWebSocket();
    showAlert('Attempting to reconnect...', 'success');
}