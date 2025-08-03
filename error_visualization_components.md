# 📊 **Error Visualization Components Specification**

## 🎯 **Overview**

This document provides comprehensive specifications for error visualization components that transform raw error data from the [`ErrorDashboardAPI`](src/python/automation/error_dashboard_api.py) into actionable visual insights. These components leverage Chart.js, D3.js, and custom visualization libraries to create an intuitive error monitoring experience.

## 📈 **Component 1: Error Trends Chart**

### **Chart Configuration**
```javascript
// Error Trends Line Chart
const errorTrendsConfig = {
    type: 'line',
    data: {
        labels: [], // Time labels (hourly/daily)
        datasets: [
            {
                label: 'Total Errors',
                data: [],
                borderColor: '#dc3545',
                backgroundColor: 'rgba(220, 53, 69, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6
            },
            {
                label: 'Critical Errors',
                data: [],
                borderColor: '#fd7e14',
                backgroundColor: 'rgba(253, 126, 20, 0.1)',
                borderWidth: 2,
                fill: false,
                tension: 0.4,
                pointRadius: 3,
                pointHoverRadius: 5
            },
            {
                label: 'Network Errors',
                data: [],
                borderColor: '#6f42c1',
                backgroundColor: 'rgba(111, 66, 193, 0.1)',
                borderWidth: 2,
                fill: false,
                tension: 0.4,
                pointRadius: 3,
                pointHoverRadius: 5
            },
            {
                label: 'Rate Limit Errors',
                data: [],
                borderColor: '#e83e8c',
                backgroundColor: 'rgba(232, 62, 140, 0.1)',
                borderWidth: 2,
                fill: false,
                tension: 0.4,
                pointRadius: 3,
                pointHoverRadius: 5
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            intersect: false,
            mode: 'index'
        },
        plugins: {
            title: {
                display: true,
                text: 'Error Trends Over Time',
                font: {
                    size: 16,
                    weight: 'bold'
                }
            },
            legend: {
                position: 'top',
                labels: {
                    usePointStyle: true,
                    padding: 20
                }
            },
            tooltip: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                titleColor: '#fff',
                bodyColor: '#fff',
                borderColor: '#dee2e6',
                borderWidth: 1,
                callbacks: {
                    title: function(context) {
                        return `Time: ${context[0].label}`;
                    },
                    label: function(context) {
                        return `${context.dataset.label}: ${context.parsed.y} errors`;
                    },
                    afterBody: function(context) {
                        const total = context.reduce((sum, item) => sum + item.parsed.y, 0);
                        return `Total: ${total} errors`;
                    }
                }
            }
        },
        scales: {
            x: {
                display: true,
                title: {
                    display: true,
                    text: 'Time',
                    font: {
                        weight: 'bold'
                    }
                },
                grid: {
                    color: 'rgba(0, 0, 0, 0.1)'
                }
            },
            y: {
                display: true,
                title: {
                    display: true,
                    text: 'Error Count',
                    font: {
                        weight: 'bold'
                    }
                },
                beginAtZero: true,
                grid: {
                    color: 'rgba(0, 0, 0, 0.1)'
                },
                ticks: {
                    precision: 0
                }
            }
        },
        elements: {
            point: {
                hoverBackgroundColor: '#fff',
                hoverBorderWidth: 2
            }
        }
    }
};
```

### **Data Integration**
```javascript
// Update error trends chart with API data
async function updateErrorTrendsChart() {
    try {
        const response = await fetch('/api/error-dashboard/trends?timeRange=24h');
        const data = await response.json();
        
        const chart = Chart.getChart('errorTrendsChart');
        
        // Update labels (timestamps)
        chart.data.labels = data.timestamps.map(ts => 
            new Date(ts).toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit' 
            })
        );
        
        // Update datasets
        chart.data.datasets[0].data = data.total_errors;
        chart.data.datasets[1].data = data.critical_errors;
        chart.data.datasets[2].data = data.network_errors;
        chart.data.datasets[3].data = data.rate_limit_errors;
        
        // Add annotations for anomalies
        if (data.anomalies && data.anomalies.length > 0) {
            chart.options.plugins.annotation = {
                annotations: data.anomalies.map(anomaly => ({
                    type: 'point',
                    xValue: anomaly.timestamp,
                    yValue: anomaly.value,
                    backgroundColor: 'rgba(255, 99, 132, 0.8)',
                    borderColor: 'rgb(255, 99, 132)',
                    borderWidth: 2,
                    radius: 8,
                    label: {
                        content: 'Anomaly',
                        enabled: true,
                        position: 'top'
                    }
                }))
            };
        }
        
        chart.update('active');
        
    } catch (error) {
        console.error('Failed to update error trends chart:', error);
        showErrorMessage('Unable to load error trends data');
    }
}
```

## 🥧 **Component 2: Error Distribution Donut Chart**

### **Chart Configuration**
```javascript
// Error Distribution Donut Chart
const errorDistributionConfig = {
    type: 'doughnut',
    data: {
        labels: ['Network Errors', 'Rate Limit', 'Authentication', 'Validation', 'System', 'Other'],
        datasets: [{
            data: [],
            backgroundColor: [
                '#6f42c1', // Network - Purple
                '#e83e8c', // Rate Limit - Pink
                '#fd7e14', // Authentication - Orange
                '#ffc107', // Validation - Yellow
                '#dc3545', // System - Red
                '#6c757d'  // Other - Gray
            ],
            borderColor: '#fff',
            borderWidth: 2,
            hoverBorderWidth: 3,
            hoverOffset: 10
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '60%',
        plugins: {
            title: {
                display: true,
                text: 'Error Distribution by Type',
                font: {
                    size: 16,
                    weight: 'bold'
                }
            },
            legend: {
                position: 'right',
                labels: {
                    usePointStyle: true,
                    padding: 15,
                    generateLabels: function(chart) {
                        const data = chart.data;
                        if (data.labels.length && data.datasets.length) {
                            return data.labels.map((label, i) => {
                                const dataset = data.datasets[0];
                                const value = dataset.data[i];
                                const total = dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                
                                return {
                                    text: `${label}: ${value} (${percentage}%)`,
                                    fillStyle: dataset.backgroundColor[i],
                                    strokeStyle: dataset.borderColor,
                                    lineWidth: dataset.borderWidth,
                                    hidden: false,
                                    index: i
                                };
                            });
                        }
                        return [];
                    }
                }
            },
            tooltip: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                titleColor: '#fff',
                bodyColor: '#fff',
                callbacks: {
                    label: function(context) {
                        const label = context.label || '';
                        const value = context.parsed;
                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                        const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                        return `${label}: ${value} errors (${percentage}%)`;
                    }
                }
            }
        },
        onHover: (event, activeElements) => {
            event.native.target.style.cursor = activeElements.length > 0 ? 'pointer' : 'default';
        },
        onClick: (event, activeElements) => {
            if (activeElements.length > 0) {
                const index = activeElements[0].index;
                const errorType = event.chart.data.labels[index];
                filterErrorsByType(errorType);
            }
        }
    }
};
```

### **Center Text Plugin**
```javascript
// Custom plugin for center text in donut chart
const centerTextPlugin = {
    id: 'centerText',
    beforeDraw: function(chart) {
        if (chart.config.type === 'doughnut') {
            const ctx = chart.ctx;
            const centerX = (chart.chartArea.left + chart.chartArea.right) / 2;
            const centerY = (chart.chartArea.top + chart.chartArea.bottom) / 2;
            
            const total = chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
            
            ctx.save();
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            
            // Total errors text
            ctx.font = 'bold 24px Arial';
            ctx.fillStyle = '#333';
            ctx.fillText(total.toString(), centerX, centerY - 10);
            
            // Label text
            ctx.font = '14px Arial';
            ctx.fillStyle = '#666';
            ctx.fillText('Total Errors', centerX, centerY + 15);
            
            ctx.restore();
        }
    }
};

Chart.register(centerTextPlugin);
```

## 📊 **Component 3: Regional Error Heatmap**

### **Heatmap Implementation**
```javascript
// Regional Error Heatmap using D3.js
class RegionalErrorHeatmap {
    constructor(containerId, data) {
        this.container = d3.select(`#${containerId}`);
        this.data = data;
        this.margin = { top: 20, right: 80, bottom: 60, left: 100 };
        this.width = 800 - this.margin.left - this.margin.right;
        this.height = 400 - this.margin.top - this.margin.bottom;
        
        this.init();
    }
    
    init() {
        // Clear existing content
        this.container.selectAll("*").remove();
        
        // Create SVG
        this.svg = this.container
            .append("svg")
            .attr("width", this.width + this.margin.left + this.margin.right)
            .attr("height", this.height + this.margin.top + this.margin.bottom);
            
        this.g = this.svg
            .append("g")
            .attr("transform", `translate(${this.margin.left},${this.margin.top})`);
        
        this.createScales();
        this.createAxes();
        this.createHeatmap();
        this.createLegend();
        this.createTooltip();
    }
    
    createScales() {
        // Get unique regions and error types
        this.regions = [...new Set(this.data.map(d => d.region))];
        this.errorTypes = [...new Set(this.data.map(d => d.error_type))];
        
        // Create scales
        this.xScale = d3.scaleBand()
            .domain(this.errorTypes)
            .range([0, this.width])
            .padding(0.1);
            
        this.yScale = d3.scaleBand()
            .domain(this.regions)
            .range([0, this.height])
            .padding(0.1);
            
        // Color scale for error intensity
        const maxErrors = d3.max(this.data, d => d.error_count);
        this.colorScale = d3.scaleSequential(d3.interpolateReds)
            .domain([0, maxErrors]);
    }
    
    createAxes() {
        // X-axis
        this.g.append("g")
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${this.height})`)
            .call(d3.axisBottom(this.xScale))
            .selectAll("text")
            .style("text-anchor", "end")
            .attr("dx", "-.8em")
            .attr("dy", ".15em")
            .attr("transform", "rotate(-45)");
            
        // Y-axis
        this.g.append("g")
            .attr("class", "y-axis")
            .call(d3.axisLeft(this.yScale));
            
        // Axis labels
        this.g.append("text")
            .attr("class", "axis-label")
            .attr("x", this.width / 2)
            .attr("y", this.height + 50)
            .style("text-anchor", "middle")
            .text("Error Type");
            
        this.g.append("text")
            .attr("class", "axis-label")
            .attr("transform", "rotate(-90)")
            .attr("x", -this.height / 2)
            .attr("y", -60)
            .style("text-anchor", "middle")
            .text("Region");
    }
    
    createHeatmap() {
        const tooltip = this.tooltip;
        const colorScale = this.colorScale;
        
        this.g.selectAll(".heatmap-cell")
            .data(this.data)
            .enter()
            .append("rect")
            .attr("class", "heatmap-cell")
            .attr("x", d => this.xScale(d.error_type))
            .attr("y", d => this.yScale(d.region))
            .attr("width", this.xScale.bandwidth())
            .attr("height", this.yScale.bandwidth())
            .attr("fill", d => colorScale(d.error_count))
            .attr("stroke", "#fff")
            .attr("stroke-width", 1)
            .style("cursor", "pointer")
            .on("mouseover", function(event, d) {
                // Highlight cell
                d3.select(this)
                    .attr("stroke", "#333")
                    .attr("stroke-width", 2);
                    
                // Show tooltip
                tooltip.transition()
                    .duration(200)
                    .style("opacity", .9);
                    
                tooltip.html(`
                    <strong>${d.region}</strong><br/>
                    Error Type: ${d.error_type}<br/>
                    Count: ${d.error_count}<br/>
                    Rate: ${d.error_rate}%<br/>
                    Last Occurrence: ${new Date(d.last_occurrence).toLocaleString()}
                `)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            })
            .on("mouseout", function(d) {
                // Remove highlight
                d3.select(this)
                    .attr("stroke", "#fff")
                    .attr("stroke-width", 1);
                    
                // Hide tooltip
                tooltip.transition()
                    .duration(500)
                    .style("opacity", 0);
            })
            .on("click", function(event, d) {
                // Drill down to specific region/error type
                showRegionalErrorDetails(d.region, d.error_type);
            });
    }
    
    createLegend() {
        const legendWidth = 20;
        const legendHeight = 200;
        
        // Create gradient definition
        const defs = this.svg.append("defs");
        const gradient = defs.append("linearGradient")
            .attr("id", "heatmap-gradient")
            .attr("x1", "0%")
            .attr("y1", "100%")
            .attr("x2", "0%")
            .attr("y2", "0%");
            
        // Add color stops
        const colorStops = d3.range(0, 1.1, 0.1);
        gradient.selectAll("stop")
            .data(colorStops)
            .enter()
            .append("stop")
            .attr("offset", d => `${d * 100}%`)
            .attr("stop-color", d => this.colorScale(d * d3.max(this.data, d => d.error_count)));
            
        // Add legend rectangle
        this.svg.append("rect")
            .attr("x", this.width + this.margin.left + 20)
            .attr("y", this.margin.top)
            .attr("width", legendWidth)
            .attr("height", legendHeight)
            .style("fill", "url(#heatmap-gradient)")
            .attr("stroke", "#333")
            .attr("stroke-width", 1);
            
        // Add legend scale
        const legendScale = d3.scaleLinear()
            .domain([0, d3.max(this.data, d => d.error_count)])
            .range([legendHeight, 0]);
            
        const legendAxis = d3.axisRight(legendScale)
            .ticks(5)
            .tickFormat(d3.format("d"));
            
        this.svg.append("g")
            .attr("class", "legend-axis")
            .attr("transform", `translate(${this.width + this.margin.left + 40},${this.margin.top})`)
            .call(legendAxis);
            
        // Legend title
        this.svg.append("text")
            .attr("class", "legend-title")
            .attr("x", this.width + this.margin.left + 50)
            .attr("y", this.margin.top - 5)
            .style("text-anchor", "middle")
            .style("font-weight", "bold")
            .text("Error Count");
    }
    
    createTooltip() {
        this.tooltip = d3.select("body")
            .append("div")
            .attr("class", "heatmap-tooltip")
            .style("opacity", 0)
            .style("position", "absolute")
            .style("background", "rgba(0, 0, 0, 0.8)")
            .style("color", "white")
            .style("padding", "10px")
            .style("border-radius", "5px")
            .style("font-size", "12px")
            .style("pointer-events", "none");
    }
    
    update(newData) {
        this.data = newData;
        this.init(); // Recreate the heatmap with new data
    }
}
```

## 📈 **Component 4: Error Rate Gauge Chart**

### **Gauge Implementation**
```javascript
// Error Rate Gauge Chart
class ErrorRateGauge {
    constructor(containerId, options = {}) {
        this.container = d3.select(`#${containerId}`);
        this.options = {
            size: 200,
            clipWidth: 200,
            clipHeight: 110,
            ringInset: 20,
            ringWidth: 20,
            pointerWidth: 10,
            pointerTailLength: 5,
            pointerHeadLengthPercent: 0.9,
            minValue: 0,
            maxValue: 100,
            minAngle: -90,
            maxAngle: 90,
            transitionMs: 750,
            majorTicks: 5,
            labelFormat: d3.format('d'),
            labelInset: 10,
            arcColorFn: d3.interpolateRdYlGn,
            ...options
        };
        
        this.range = this.options.maxValue - this.options.minValue;
        this.r = this.options.size / 2;
        this.pointerHeadLength = Math.round(this.r * this.options.pointerHeadLengthPercent);
        
        this.init();
    }
    
    init() {
        this.container.selectAll("*").remove();
        
        this.svg = this.container
            .append("svg")
            .attr("width", this.options.clipWidth)
            .attr("height", this.options.clipHeight);
            
        this.g = this.svg
            .append("g")
            .attr("transform", `translate(${this.options.clipWidth / 2}, ${this.options.clipHeight})`);
            
        this.createScale();
        this.createArcs();
        this.createTicks();
        this.createPointer();
        this.createLabels();
    }
    
    createScale() {
        this.scale = d3.scaleLinear()
            .range([this.options.minAngle, this.options.maxAngle])
            .domain([this.options.minValue, this.options.maxValue]);
    }
    
    createArcs() {
        const arc = d3.arc()
            .innerRadius(this.r - this.options.ringWidth - this.options.ringInset)
            .outerRadius(this.r - this.options.ringInset)
            .startAngle((d, i) => {
                const ratio = d * i;
                return this.deg2rad(this.options.minAngle + (ratio * this.range));
            })
            .endAngle((d, i) => {
                const ratio = d * (i + 1);
                return this.deg2rad(this.options.minAngle + (ratio * this.range));
            });
            
        const arcs = this.g.append("g")
            .attr("class", "arc")
            .selectAll("path")
            .data(d3.range(1, this.options.majorTicks + 1).map(d => 1 / this.options.majorTicks))
            .enter()
            .append("path")
            .attr("fill", (d, i) => {
                const ratio = (i + 1) / this.options.majorTicks;
                return this.options.arcColorFn(1 - ratio); // Reverse for red-to-green
            })
            .attr("d", arc);
    }
    
    createTicks() {
        const lg = this.g.append("g")
            .attr("class", "label")
            .attr("text-anchor", "middle");
            
        const ticks = this.scale.ticks(this.options.majorTicks);
        
        lg.selectAll("text")
            .data(ticks)
            .enter()
            .append("text")
            .attr("transform", d => {
                const ratio = this.scale(d);
                const newAngle = this.options.minAngle + (ratio * this.range);
                return `rotate(${newAngle}) translate(0,${this.options.labelInset - this.r})`;
            })
            .text(this.options.labelFormat)
            .style("font-size", "12px")
            .style("font-weight", "bold")
            .style("fill", "#333");
    }
    
    createPointer() {
        const lineData = [
            [this.options.pointerWidth / 2, 0],
            [0, -this.pointerHeadLength],
            [-(this.options.pointerWidth / 2), 0],
            [0, this.options.pointerTailLength],
            [this.options.pointerWidth / 2, 0]
        ];
        
        const pointerLine = d3.line().curve(d3.curveLinear);
        
        this.pointer = this.g.append("path")
            .data([lineData])
            .attr("class", "pointer")
            .attr("d", pointerLine)
            .attr("transform", `rotate(${this.options.minAngle})`)
            .style("fill", "#333")
            .style("stroke", "#333")
            .style("stroke-width", 1);
            
        // Center circle
        this.g.append("circle")
            .attr("class", "pointer-center")
            .attr("cx", 0)
            .attr("cy", 0)
            .attr("r", this.options.pointerWidth)
            .style("fill", "#333")
            .style("stroke", "#fff")
            .style("stroke-width", 2);
    }
    
    createLabels() {
        // Title
        this.g.append("text")
            .attr("class", "gauge-title")
            .attr("x", 0)
            .attr("y", -this.r + 30)
            .attr("text-anchor", "middle")
            .style("font-size", "16px")
            .style("font-weight", "bold")
            .style("fill", "#333")
            .text("Error Rate %");
            
        // Current value
        this.valueText = this.g.append("text")
            .attr("class", "gauge-value")
            .attr("x", 0)
            .attr("y", -20)
            .attr("text-anchor", "middle")
            .style("font-size", "24px")
            .style("font-weight", "bold")
            .style("fill", "#333")
            .text("0%");
    }
    
    update(value) {
        const newAngle = this.options.minAngle + (this.scale(value) * this.range);
        
        this.pointer
            .transition()
            .duration(this.options.transitionMs)
            .ease(d3.easeElastic)
            .attr("transform", `rotate(${newAngle})`);
            
        this.valueText
            .transition()
            .duration(this.options.transitionMs)
            .tween("text", () => {
                const i = d3.interpolate(this.currentValue || 0, value);
                return t => {
                    this.valueText.text(Math.round(i(t)) + "%");
                };
            });
            
        this.currentValue = value;
    }
    
    deg2rad(deg) {
        return deg * Math.PI / 180;
    }
}
```

## 📊 **Component 5: Error Timeline Visualization**

### **Timeline Implementation**
```javascript
// Error Timeline Visualization
class ErrorTimeline {
    constructor(containerId, data) {
        this.container = d3.select(`#${containerId}`);
        this.data = data;
        this.margin = { top: 20, right: 30, bottom: 40, left: 50 };
        this.width = 900 - this.margin.left - this.margin.right;
        this.height = 300 - this.margin.top - this.margin.bottom;
        
        this.init();
    }
    
    init() {
        this.container.selectAll("*").remove();
        
        this.svg = this.container
            .append("svg")
            .attr("width", this.width + this.margin.left + this.margin.right)
            .attr("height", this.height + this.margin.top + this.margin.bottom);
            
        this.g = this.svg
            .append("g")
            .attr("transform", `translate(${this.margin.left},${this.margin.top})`);
            
        this.createScales();
        this.createAxes();
        this.createTimeline();
        this.createBrush();
        this.createTooltip();
    }
    
    createScales() {
        // Parse dates
        this.data.forEach(d => {
            d.timestamp = new Date(d.timestamp);
        });
        
        // Time scale
        this.xScale = d3.scaleTime()
            .domain(d3.extent(this.data, d => d.timestamp))
            .range([0, this.width]);
            
        // Severity scale for y-position
        const severityOrder = ['low', 'medium', 'high', 'critical'];
        this.yScale = d3.scaleBand()
            .domain(severityOrder)
            .range([this.height, 0])
            .padding(0.1);
            
        // Color scale for error types
        this.colorScale = d3.scaleOrdinal()
            .domain(['network', 'rate_limit', 'authentication', 'validation', 'system'])
            .range(['#6f42c1', '#e83e8c', '#fd7e14', '#ffc107', '#dc3545']);
            
        // Size scale for impact
        this.sizeScale = d3.scaleSqrt()
            .domain(d3.extent(this.data, d => d.impact_score))
            .range([4, 20]);
    }
    
    createAxes() {
        // X-axis (time)
        this.xAxis = d3.axisBottom(this.xScale)
            .tickFormat(d3.timeFormat("%H:%M"));
            
        this.g.append("g")
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${this.height})`)
            .call(this.xAxis);
            
        // Y-axis (severity)
        this.yAxis = d3.axisLeft(this.yScale);
        
        this.g.append("g")
            .attr("class", "y-axis")
            .call(this.yAxis);
            
        // Axis labels
        this.g.append("text")
            .attr("class", "axis-label")
            .attr("x", this.width / 2)
            .attr("y", this.height + 35)
            .style("text-anchor", "middle")
            .text("Time");
            
        this.g.append("text")
            .attr("class", "axis-label")
            .attr("transform", "rotate(-90)")
            .attr("x", -this.height / 2)
            .attr("y", -35)
            .style("text-anchor",
"middle")
            .text("Severity");
    }
    
    createTimeline() {
        const tooltip = this.tooltip;
        
        this.g.selectAll(".error-event")
            .data(this.data)
            .enter()
            .append("circle")
            .attr("class", "error-event")
            .attr("cx", d => this.xScale(d.timestamp))
            .attr("cy", d => this.yScale(d.severity) + this.yScale.bandwidth() / 2)
            .attr("r", d => this.sizeScale(d.impact_score))
            .attr("fill", d => this.colorScale(d.error_type))
            .attr("stroke", "#fff")
            .attr("stroke-width", 1)
            .style("cursor", "pointer")
            .on("mouseover", function(event, d) {
                d3.select(this)
                    .attr("stroke", "#333")
                    .attr("stroke-width", 2);
                    
                tooltip.transition()
                    .duration(200)
                    .style("opacity", .9);
                    
                tooltip.html(`
                    <strong>Error Event</strong><br/>
                    Time: ${d.timestamp.toLocaleString()}<br/>
                    Type: ${d.error_type}<br/>
                    Severity: ${d.severity}<br/>
                    Message: ${d.message}<br/>
                    Impact Score: ${d.impact_score}/10<br/>
                    Request ID: ${d.request_id}
                `)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            })
            .on("mouseout", function(d) {
                d3.select(this)
                    .attr("stroke", "#fff")
                    .attr("stroke-width", 1);
                    
                tooltip.transition()
                    .duration(500)
                    .style("opacity", 0);
            })
            .on("click", function(event, d) {
                showErrorDetails(d.error_id);
            });
    }
    
    createBrush() {
        const brush = d3.brushX()
            .extent([[0, 0], [this.width, this.height]])
            .on("brush end", (event) => {
                if (!event.selection) return;
                
                const [x0, x1] = event.selection;
                const timeRange = [
                    this.xScale.invert(x0),
                    this.xScale.invert(x1)
                ];
                
                this.onTimeRangeSelected(timeRange);
            });
            
        this.g.append("g")
            .attr("class", "brush")
            .call(brush);
    }
    
    createTooltip() {
        this.tooltip = d3.select("body")
            .append("div")
            .attr("class", "timeline-tooltip")
            .style("opacity", 0)
            .style("position", "absolute")
            .style("background", "rgba(0, 0, 0, 0.8)")
            .style("color", "white")
            .style("padding", "10px")
            .style("border-radius", "5px")
            .style("font-size", "12px")
            .style("pointer-events", "none");
    }
    
    onTimeRangeSelected(timeRange) {
        // Filter errors by time range
        filterErrorsByTimeRange(timeRange[0], timeRange[1]);
    }
    
    update(newData) {
        this.data = newData;
        this.init(); // Recreate timeline with new data
    }
}
```

## 📊 **Component 6: Error Correlation Matrix**

### **Matrix Implementation**
```javascript
// Error Correlation Matrix
class ErrorCorrelationMatrix {
    constructor(containerId, data) {
        this.container = d3.select(`#${containerId}`);
        this.data = data;
        this.margin = { top: 50, right: 50, bottom: 100, left: 100 };
        this.width = 600 - this.margin.left - this.margin.right;
        this.height = 600 - this.margin.top - this.margin.bottom;
        
        this.init();
    }
    
    init() {
        this.container.selectAll("*").remove();
        
        this.svg = this.container
            .append("svg")
            .attr("width", this.width + this.margin.left + this.margin.right)
            .attr("height", this.height + this.margin.top + this.margin.bottom);
            
        this.g = this.svg
            .append("g")
            .attr("transform", `translate(${this.margin.left},${this.margin.top})`);
            
        this.createScales();
        this.createMatrix();
        this.createAxes();
        this.createLegend();
        this.createTooltip();
    }
    
    createScales() {
        // Get unique error types
        this.errorTypes = [...new Set([
            ...this.data.map(d => d.error_type_1),
            ...this.data.map(d => d.error_type_2)
        ])];
        
        // Create scales
        this.xScale = d3.scaleBand()
            .domain(this.errorTypes)
            .range([0, this.width])
            .padding(0.05);
            
        this.yScale = d3.scaleBand()
            .domain(this.errorTypes)
            .range([0, this.height])
            .padding(0.05);
            
        // Color scale for correlation strength
        this.colorScale = d3.scaleSequential(d3.interpolateRdBu)
            .domain([-1, 1]); // Correlation ranges from -1 to 1
    }
    
    createMatrix() {
        const tooltip = this.tooltip;
        const colorScale = this.colorScale;
        
        // Create correlation matrix data
        const matrixData = [];
        this.errorTypes.forEach(type1 => {
            this.errorTypes.forEach(type2 => {
                const correlation = this.getCorrelation(type1, type2);
                matrixData.push({
                    type1: type1,
                    type2: type2,
                    correlation: correlation,
                    count: this.getCoOccurrenceCount(type1, type2)
                });
            });
        });
        
        this.g.selectAll(".correlation-cell")
            .data(matrixData)
            .enter()
            .append("rect")
            .attr("class", "correlation-cell")
            .attr("x", d => this.xScale(d.type1))
            .attr("y", d => this.yScale(d.type2))
            .attr("width", this.xScale.bandwidth())
            .attr("height", this.yScale.bandwidth())
            .attr("fill", d => colorScale(d.correlation))
            .attr("stroke", "#fff")
            .attr("stroke-width", 1)
            .style("cursor", "pointer")
            .on("mouseover", function(event, d) {
                d3.select(this)
                    .attr("stroke", "#333")
                    .attr("stroke-width", 2);
                    
                tooltip.transition()
                    .duration(200)
                    .style("opacity", .9);
                    
                const correlationText = d.correlation > 0 ? "Positive" : 
                                      d.correlation < 0 ? "Negative" : "No";
                                      
                tooltip.html(`
                    <strong>Error Correlation</strong><br/>
                    ${d.type1} ↔ ${d.type2}<br/>
                    Correlation: ${d.correlation.toFixed(3)}<br/>
                    Strength: ${correlationText}<br/>
                    Co-occurrences: ${d.count}
                `)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            })
            .on("mouseout", function(d) {
                d3.select(this)
                    .attr("stroke", "#fff")
                    .attr("stroke-width", 1);
                    
                tooltip.transition()
                    .duration(500)
                    .style("opacity", 0);
            })
            .on("click", function(event, d) {
                showCorrelationDetails(d.type1, d.type2);
            });
            
        // Add correlation values as text
        this.g.selectAll(".correlation-text")
            .data(matrixData)
            .enter()
            .append("text")
            .attr("class", "correlation-text")
            .attr("x", d => this.xScale(d.type1) + this.xScale.bandwidth() / 2)
            .attr("y", d => this.yScale(d.type2) + this.yScale.bandwidth() / 2)
            .attr("text-anchor", "middle")
            .attr("dominant-baseline", "middle")
            .style("font-size", "10px")
            .style("font-weight", "bold")
            .style("fill", d => Math.abs(d.correlation) > 0.5 ? "#fff" : "#333")
            .style("pointer-events", "none")
            .text(d => d.correlation.toFixed(2));
    }
    
    createAxes() {
        // X-axis
        this.g.append("g")
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${this.height})`)
            .call(d3.axisBottom(this.xScale))
            .selectAll("text")
            .style("text-anchor", "end")
            .attr("dx", "-.8em")
            .attr("dy", ".15em")
            .attr("transform", "rotate(-45)");
            
        // Y-axis
        this.g.append("g")
            .attr("class", "y-axis")
            .call(d3.axisLeft(this.yScale));
            
        // Axis labels
        this.g.append("text")
            .attr("class", "axis-label")
            .attr("x", this.width / 2)
            .attr("y", this.height + 80)
            .style("text-anchor", "middle")
            .style("font-weight", "bold")
            .text("Error Type");
            
        this.g.append("text")
            .attr("class", "axis-label")
            .attr("transform", "rotate(-90)")
            .attr("x", -this.height / 2)
            .attr("y", -60)
            .style("text-anchor", "middle")
            .style("font-weight", "bold")
            .text("Error Type");
    }
    
    createLegend() {
        const legendWidth = 20;
        const legendHeight = 200;
        
        // Create gradient definition
        const defs = this.svg.append("defs");
        const gradient = defs.append("linearGradient")
            .attr("id", "correlation-gradient")
            .attr("x1", "0%")
            .attr("y1", "100%")
            .attr("x2", "0%")
            .attr("y2", "0%");
            
        // Add color stops
        const colorStops = d3.range(-1, 1.1, 0.2);
        gradient.selectAll("stop")
            .data(colorStops)
            .enter()
            .append("stop")
            .attr("offset", d => `${((d + 1) / 2) * 100}%`)
            .attr("stop-color", d => this.colorScale(d));
            
        // Add legend rectangle
        this.svg.append("rect")
            .attr("x", this.width + this.margin.left + 20)
            .attr("y", this.margin.top)
            .attr("width", legendWidth)
            .attr("height", legendHeight)
            .style("fill", "url(#correlation-gradient)")
            .attr("stroke", "#333")
            .attr("stroke-width", 1);
            
        // Add legend scale
        const legendScale = d3.scaleLinear()
            .domain([-1, 1])
            .range([legendHeight, 0]);
            
        const legendAxis = d3.axisRight(legendScale)
            .ticks(5)
            .tickFormat(d3.format(".1f"));
            
        this.svg.append("g")
            .attr("class", "legend-axis")
            .attr("transform", `translate(${this.width + this.margin.left + 40},${this.margin.top})`)
            .call(legendAxis);
            
        // Legend title
        this.svg.append("text")
            .attr("class", "legend-title")
            .attr("x", this.width + this.margin.left + 50)
            .attr("y", this.margin.top - 10)
            .style("text-anchor", "middle")
            .style("font-weight", "bold")
            .text("Correlation");
    }
    
    createTooltip() {
        this.tooltip = d3.select("body")
            .append("div")
            .attr("class", "correlation-tooltip")
            .style("opacity", 0)
            .style("position", "absolute")
            .style("background", "rgba(0, 0, 0, 0.8)")
            .style("color", "white")
            .style("padding", "10px")
            .style("border-radius", "5px")
            .style("font-size", "12px")
            .style("pointer-events", "none");
    }
    
    getCorrelation(type1, type2) {
        // Find correlation data for the pair
        const correlation = this.data.find(d => 
            (d.error_type_1 === type1 && d.error_type_2 === type2) ||
            (d.error_type_1 === type2 && d.error_type_2 === type1)
        );
        
        return correlation ? correlation.correlation_coefficient : 0;
    }
    
    getCoOccurrenceCount(type1, type2) {
        // Find co-occurrence count for the pair
        const correlation = this.data.find(d => 
            (d.error_type_1 === type1 && d.error_type_2 === type2) ||
            (d.error_type_1 === type2 && d.error_type_2 === type1)
        );
        
        return correlation ? correlation.co_occurrence_count : 0;
    }
    
    update(newData) {
        this.data = newData;
        this.init(); // Recreate matrix with new data
    }
}
```

## 📊 **Component 7: Error Metrics Dashboard Table**

### **Advanced Data Table Implementation**
```javascript
// Error Metrics Dashboard Table
class ErrorMetricsTable {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            pageSize: 25,
            sortable: true,
            filterable: true,
            exportable: true,
            selectable: true,
            ...options
        };
        
        this.data = [];
        this.filteredData = [];
        this.currentPage = 1;
        this.sortColumn = null;
        this.sortDirection = 'asc';
        this.selectedRows = new Set();
        
        this.init();
    }
    
    init() {
        this.createTableStructure();
        this.createControls();
        this.createPagination();
        this.bindEvents();
    }
    
    createTableStructure() {
        this.container.innerHTML = `
            <div class="error-table-container">
                <div class="table-controls">
                    <div class="table-search">
                        <input type="text" id="tableSearch" placeholder="Search errors..." class="form-control">
                    </div>
                    <div class="table-filters">
                        <select id="severityFilter" class="form-select">
                            <option value="">All Severities</option>
                            <option value="critical">Critical</option>
                            <option value="high">High</option>
                            <option value="medium">Medium</option>
                            <option value="low">Low</option>
                        </select>
                        <select id="typeFilter" class="form-select">
                            <option value="">All Types</option>
                            <option value="network">Network</option>
                            <option value="rate_limit">Rate Limit</option>
                            <option value="authentication">Authentication</option>
                            <option value="validation">Validation</option>
                        </select>
                    </div>
                    <div class="table-actions">
                        <button id="exportBtn" class="btn btn-outline-primary">
                            <i class="fas fa-download"></i> Export
                        </button>
                        <button id="refreshBtn" class="btn btn-outline-secondary">
                            <i class="fas fa-sync-alt"></i> Refresh
                        </button>
                    </div>
                </div>
                
                <div class="table-responsive">
                    <table class="table table-striped table-hover">
                        <thead class="table-dark">
                            <tr>
                                <th class="select-column">
                                    <input type="checkbox" id="selectAll">
                                </th>
                                <th class="sortable" data-column="timestamp">
                                    Timestamp <i class="fas fa-sort"></i>
                                </th>
                                <th class="sortable" data-column="severity">
                                    Severity <i class="fas fa-sort"></i>
                                </th>
                                <th class="sortable" data-column="error_type">
                                    Type <i class="fas fa-sort"></i>
                                </th>
                                <th class="sortable" data-column="message">
                                    Message <i class="fas fa-sort"></i>
                                </th>
                                <th class="sortable" data-column="region">
                                    Region <i class="fas fa-sort"></i>
                                </th>
                                <th class="sortable" data-column="request_id">
                                    Request ID <i class="fas fa-sort"></i>
                                </th>
                                <th class="sortable" data-column="retry_count">
                                    Retries <i class="fas fa-sort"></i>
                                </th>
                                <th class="actions-column">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody">
                            <!-- Table rows will be populated here -->
                        </tbody>
                    </table>
                </div>
                
                <div class="table-footer">
                    <div class="table-info">
                        <span id="tableInfo">Showing 0 of 0 entries</span>
                    </div>
                    <div class="table-pagination">
                        <nav>
                            <ul class="pagination pagination-sm" id="pagination">
                                <!-- Pagination will be populated here -->
                            </ul>
                        </nav>
                    </div>
                </div>
            </div>
        `;
    }
    
    createControls() {
        // Search functionality
        const searchInput = document.getElementById('tableSearch');
        searchInput.addEventListener('input', (e) => {
            this.filterData();
        });
        
        // Filter functionality
        const severityFilter = document.getElementById('severityFilter');
        const typeFilter = document.getElementById('typeFilter');
        
        severityFilter.addEventListener('change', () => this.filterData());
        typeFilter.addEventListener('change', () => this.filterData());
        
        // Export functionality
        document.getElementById('exportBtn').addEventListener('click', () => {
            this.exportData();
        });
        
        // Refresh functionality
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.refreshData();
        });
        
        // Select all functionality
        document.getElementById('selectAll').addEventListener('change', (e) => {
            this.toggleSelectAll(e.target.checked);
        });
    }
    
    createPagination() {
        const totalPages = Math.ceil(this.filteredData.length / this.options.pageSize);
        const pagination = document.getElementById('pagination');
        
        pagination.innerHTML = '';
        
        // Previous button
        const prevLi = document.createElement('li');
        prevLi.className = `page-item ${this.currentPage === 1 ? 'disabled' : ''}`;
        prevLi.innerHTML = '<a class="page-link" href="#" data-page="prev">Previous</a>';
        pagination.appendChild(prevLi);
        
        // Page numbers
        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(totalPages, this.currentPage + 2);
        
        for (let i = startPage; i <= endPage; i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === this.currentPage ? 'active' : ''}`;
            li.innerHTML = `<a class="page-link" href="#" data-page="${i}">${i}</a>`;
            pagination.appendChild(li);
        }
        
        // Next button
        const nextLi = document.createElement('li');
        nextLi.className = `page-item ${this.currentPage === totalPages ? 'disabled' : ''}`;
        nextLi.innerHTML = '<a class="page-link" href="#" data-page="next">Next</a>';
        pagination.appendChild(nextLi);
        
        // Bind pagination events
        pagination.addEventListener('click', (e) => {
            e.preventDefault();
            if (e.target.classList.contains('page-link')) {
                const page = e.target.dataset.page;
                this.goToPage(page);
            }
        });
    }
    
    bindEvents() {
        // Sortable headers
        const sortableHeaders = this.container.querySelectorAll('.sortable');
        sortableHeaders.forEach(header => {
            header.addEventListener('click', () => {
                const column = header.dataset.column;
                this.sortData(column);
            });
        });
    }
    
    loadData(data) {
        this.data = data;
        this.filteredData = [...data];
        this.renderTable();
        this.updateTableInfo();
        this.createPagination();
    }
    
    renderTable() {
        const tbody = document.getElementById('tableBody');
        const startIndex = (this.currentPage - 1) * this.options.pageSize;
        const endIndex = startIndex + this.options.pageSize;
        const pageData = this.filteredData.slice(startIndex, endIndex);
        
        tbody.innerHTML = '';
        
        pageData.forEach(row => {
            const tr = document.createElement('tr');
            tr.dataset.errorId = row.error_id;
            
            tr.innerHTML = `
                <td class="select-column">
                    <input type="checkbox" class="row-select" value="${row.error_id}">
                </td>
                <td>
                    <span class="timestamp" title="${new Date(row.timestamp).toLocaleString()}">
                        ${this.formatRelativeTime(row.timestamp)}
                    </span>
                </td>
                <td>
                    <span class="badge severity-${row.severity}">${row.severity}</span>
                </td>
                <td>
                    <span class="badge bg-secondary">${row.error_type}</span>
                </td>
                <td class="message-cell">
                    <span class="error-message" title="${row.message}">
                        ${this.truncateText(row.message, 50)}
                    </span>
                </td>
                <td>${row.region || 'N/A'}</td>
                <td>
                    <code class="request-id">${row.request_id}</code>
                </td>
                <td>
                    <span class="retry-count">${row.retry_count}/${row.max_retries}</span>
                    <div class="progress mt-1" style="height: 3px;">
                        <div class="progress-bar" style="width: ${(row.retry_count / row.max_retries) * 100}%"></div>
                    </div>
                </td>
                <td class="actions-column">
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" onclick="viewErrorDetails('${row.error_id}')">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-outline-success" onclick="retryError('${row.error_id}')">
                            <i class="fas fa-redo"></i>
                        </button>
                        <button class="btn btn-outline-warning" onclick="resolveError('${row.error_id}')">
                            <i class="fas fa-check"></i>
                        </button>
                    </div>
                </td>
            `;
            
            tbody.appendChild(tr);
        });
        
        // Bind row selection events
        const rowSelects = tbody.querySelectorAll('.row-select');
        rowSelects.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                this.toggleRowSelection(e.target.value, e.target.checked);
            });
        });
    }
    
    filterData() {
        const searchTerm = document.getElementById('tableSearch').value.toLowerCase();
        const severityFilter = document.getElementById('severityFilter').value;
        const typeFilter = document.getElementById('typeFilter').value;
        
        this.filteredData = this.data.filter(row => {
            const matchesSearch = !searchTerm || 
                row.message.toLowerCase().includes(searchTerm) ||
                row.request_id.toLowerCase().includes(searchTerm) ||
                (row.region && row.region.toLowerCase().includes(searchTerm));
                
            const matchesSeverity = !severityFilter || row.severity === severityFilter;
            const matchesType = !typeFilter || row.error_type === typeFilter;
            
            return matchesSearch && matchesSeverity && matchesType;
        });
        
        this.currentPage = 1;
        this.renderTable();
        this.updateTableInfo();
        this.createPagination();
    }
    
    sortData(column) {
        if (this.sortColumn === column) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortColumn = column;
            this.sortDirection = 'asc';
        }
        
        this.filteredData.sort((a, b) => {
            let aVal = a[column];
            let bVal = b[column];
            
            // Handle different data types
            if (column === 'timestamp') {
                aVal = new Date(aVal);
                bVal = new Date(bVal);
            } else if (typeof aVal === 'string') {
                aVal = aVal.toLowerCase();
                bVal = bVal.toLowerCase();
            }
            
            if (aVal < bVal) return this.sortDirection === 'asc' ? -1 : 1;
            if (aVal > bVal) return this.sortDirection === 'asc' ? 1 : -1;
            return 0;
        });
        
        this.renderTable();
        this.updateSortIcons();
    }
    
    updateSortIcons() {
        // Reset all sort icons
        const sortIcons = this.container.querySelectorAll('.sortable i');
        sortIcons.forEach(icon => {
            icon.className = 'fas fa-sort';
        });
        
        // Update active sort icon
        if (this.sortColumn) {
            const activeHeader = this.container.querySelector(`[data-column="${this.sortColumn}"] i`);
            if (activeHeader) {
                activeHeader.className = `fas fa-sort-${this.sortDirection === 'asc' ? 'up' : 'down'}`;
            }
        }
    }
    
    goToPage(page) {
        const totalPages = Math.ceil(this.filteredData.length / this.options.pageSize);
        
        if (page === 'prev' && this.currentPage > 1) {
            this.currentPage--;
        } else if (page === 'next' && this.currentPage < totalPages) {
            this.currentPage++;
        } else if (typeof page === 'string' && !isNaN(page)) {
            this.currentPage = parseInt(page);
        }
        
        this.renderTable();
        this.createPagination();
        this.updateTableInfo();
    }
    
    toggleSelectAll(checked) {
        const rowSelects = this.container.querySelectorAll('.row-select');
        rowSelects.forEach(checkbox => {
            checkbox.checked = checked;
            this.toggleRowSelection(checkbox.value, checked);
        });
    }
    
    toggleRowSelection(errorId, selected) {
        if (selected) {
            this.selectedRows.add(errorId);
        } else {
            this.selectedRows.delete(errorId);
        }
        
        // Update select all checkbox
        const selectAll = document.getElementById('selectAll');
        const rowSelects = this.container.querySelectorAll('.row-select');
        const checkedRows = this.container.querySelectorAll('.row-select:checked');
        
        selectAll.indeterminate = checkedRows.length > 0 && checkedRows.length < rowSelects.length;
        selectAll.checked = checkedRows.length === rowSelects.length;
    }
    
    updateTableInfo() {
        const info = document.getElementById('tableInfo');
        const startIndex = (this.currentPage - 1) * this.options.pageSize + 1;
        const endIndex = Math.min(this.currentPage * this.options.pageSize, this.filteredData.length);
        
        info.textContent = `Showing ${startIndex} to ${endIndex} of ${this.filteredData.length} entries`;
        
        if (this.filteredData.length !== this.data.length) {
            info.textContent += ` (filtered from ${this.data.length} total entries)`;
        }
    }
    
    exportData() {
        const selectedData = this.selectedRows.size > 0 
            ? this.data.filter(row => this.selectedRows.has(row.error_id))
            : this.filteredData;
            
        const csv = this.convertToCSV(selectedData);
        this.downloadCSV(csv, 'error-report.csv');
    }
    
    convertToCSV(data) {
        const headers = ['Timestamp', 'Severity', 'Type', 'Message', 'Region', 'Request ID', 'Retry Count'];
        const csvContent = [
            headers.join(','),
            ...data.map(row => [
                new Date(row.timestamp).toISOString(),
                row.severity,
                row.error_type,
                `"${row.message.replace(/"/g, '""')}"`,
                row.region || '',
                row.request_id,
                `${row.retry_count}/${row.max_retries}`
            ].join(','))
        ].join('\n');
        
        return csvContent;
    }
    
    downloadCSV(csv, filename) {
        const blob = new Blob([csv],
{ type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }
    
    refreshData() {
        // Trigger data refresh from API
        fetchErrorData().then(data => {
            this.loadData(data);
        });
    }
    
    formatRelativeTime(timestamp) {
        const now = new Date();
        const time = new Date(timestamp);
        const diffMs = now - time;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return `${diffDays}d ago`;
    }
    
    truncateText(text, maxLength) {
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }
}
```

## 📊 **Component 8: Error Status Indicators**

### **Real-time Status Indicators Implementation**
```javascript
// Error Status Indicators
class ErrorStatusIndicators {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.indicators = {};
        this.thresholds = {
            critical: { max: 5, color: '#dc3545' },
            high: { max: 20, color: '#fd7e14' },
            medium: { max: 50, color: '#ffc107' },
            low: { max: Infinity, color: '#28a745' }
        };
        
        this.init();
    }
    
    init() {
        this.createIndicatorStructure();
        this.bindEvents();
    }
    
    createIndicatorStructure() {
        this.container.innerHTML = `
            <div class="error-status-grid">
                <div class="status-card critical-errors">
                    <div class="status-header">
                        <h5>Critical Errors</h5>
                        <i class="fas fa-exclamation-triangle"></i>
                    </div>
                    <div class="status-body">
                        <div class="status-number" id="criticalCount">0</div>
                        <div class="status-trend" id="criticalTrend">
                            <i class="fas fa-arrow-up"></i>
                            <span>+0%</span>
                        </div>
                        <div class="status-description">Last 24 hours</div>
                    </div>
                    <div class="status-footer">
                        <div class="status-bar">
                            <div class="status-progress" id="criticalProgress"></div>
                        </div>
                    </div>
                </div>
                
                <div class="status-card high-errors">
                    <div class="status-header">
                        <h5>High Priority</h5>
                        <i class="fas fa-exclamation-circle"></i>
                    </div>
                    <div class="status-body">
                        <div class="status-number" id="highCount">0</div>
                        <div class="status-trend" id="highTrend">
                            <i class="fas fa-arrow-down"></i>
                            <span>-0%</span>
                        </div>
                        <div class="status-description">Last 24 hours</div>
                    </div>
                    <div class="status-footer">
                        <div class="status-bar">
                            <div class="status-progress" id="highProgress"></div>
                        </div>
                    </div>
                </div>
                
                <div class="status-card medium-errors">
                    <div class="status-header">
                        <h5>Medium Priority</h5>
                        <i class="fas fa-exclamation"></i>
                    </div>
                    <div class="status-body">
                        <div class="status-number" id="mediumCount">0</div>
                        <div class="status-trend" id="mediumTrend">
                            <i class="fas fa-arrow-up"></i>
                            <span>+0%</span>
                        </div>
                        <div class="status-description">Last 24 hours</div>
                    </div>
                    <div class="status-footer">
                        <div class="status-bar">
                            <div class="status-progress" id="mediumProgress"></div>
                        </div>
                    </div>
                </div>
                
                <div class="status-card low-errors">
                    <div class="status-header">
                        <h5>Low Priority</h5>
                        <i class="fas fa-info-circle"></i>
                    </div>
                    <div class="status-body">
                        <div class="status-number" id="lowCount">0</div>
                        <div class="status-trend" id="lowTrend">
                            <i class="fas fa-arrow-down"></i>
                            <span>-0%</span>
                        </div>
                        <div class="status-description">Last 24 hours</div>
                    </div>
                    <div class="status-footer">
                        <div class="status-bar">
                            <div class="status-progress" id="lowProgress"></div>
                        </div>
                    </div>
                </div>
                
                <div class="status-card system-health">
                    <div class="status-header">
                        <h5>System Health</h5>
                        <i class="fas fa-heartbeat"></i>
                    </div>
                    <div class="status-body">
                        <div class="health-gauge" id="healthGauge">
                            <div class="gauge-needle" id="healthNeedle"></div>
                            <div class="gauge-value" id="healthValue">95%</div>
                        </div>
                        <div class="status-description">Overall system health</div>
                    </div>
                    <div class="status-footer">
                        <div class="health-indicators">
                            <span class="health-dot active" title="API Health"></span>
                            <span class="health-dot active" title="Database Health"></span>
                            <span class="health-dot warning" title="Network Health"></span>
                            <span class="health-dot active" title="Storage Health"></span>
                        </div>
                    </div>
                </div>
                
                <div class="status-card error-rate">
                    <div class="status-header">
                        <h5>Error Rate</h5>
                        <i class="fas fa-chart-line"></i>
                    </div>
                    <div class="status-body">
                        <div class="rate-display">
                            <span class="rate-number" id="errorRate">2.3</span>
                            <span class="rate-unit">errors/min</span>
                        </div>
                        <div class="rate-sparkline" id="rateSparkline">
                            <!-- Sparkline chart will be rendered here -->
                        </div>
                        <div class="status-description">Current error rate</div>
                    </div>
                    <div class="status-footer">
                        <div class="rate-threshold">
                            <span class="threshold-label">Threshold: 5.0/min</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    bindEvents() {
        // Add click handlers for status cards
        const statusCards = this.container.querySelectorAll('.status-card');
        statusCards.forEach(card => {
            card.addEventListener('click', (e) => {
                const cardType = card.classList[1]; // Get the second class name
                this.onStatusCardClick(cardType);
            });
        });
    }
    
    updateIndicators(data) {
        // Update error counts
        this.updateErrorCounts(data.error_counts);
        
        // Update trends
        this.updateTrends(data.trends);
        
        // Update system health
        this.updateSystemHealth(data.system_health);
        
        // Update error rate
        this.updateErrorRate(data.error_rate);
        
        // Update progress bars
        this.updateProgressBars(data.error_counts);
    }
    
    updateErrorCounts(counts) {
        document.getElementById('criticalCount').textContent = counts.critical || 0;
        document.getElementById('highCount').textContent = counts.high || 0;
        document.getElementById('mediumCount').textContent = counts.medium || 0;
        document.getElementById('lowCount').textContent = counts.low || 0;
    }
    
    updateTrends(trends) {
        const trendElements = [
            { id: 'criticalTrend', value: trends.critical || 0 },
            { id: 'highTrend', value: trends.high || 0 },
            { id: 'mediumTrend', value: trends.medium || 0 },
            { id: 'lowTrend', value: trends.low || 0 }
        ];
        
        trendElements.forEach(trend => {
            const element = document.getElementById(trend.id);
            const icon = element.querySelector('i');
            const span = element.querySelector('span');
            
            const isPositive = trend.value > 0;
            const isNegative = trend.value < 0;
            
            // Update icon
            icon.className = isPositive ? 'fas fa-arrow-up' : 
                           isNegative ? 'fas fa-arrow-down' : 'fas fa-minus';
            
            // Update text and color
            span.textContent = `${isPositive ? '+' : ''}${trend.value.toFixed(1)}%`;
            element.className = `status-trend ${isPositive ? 'trend-up' : isNegative ? 'trend-down' : 'trend-neutral'}`;
        });
    }
    
    updateSystemHealth(health) {
        const healthValue = document.getElementById('healthValue');
        const healthNeedle = document.getElementById('healthNeedle');
        const healthGauge = document.getElementById('healthGauge');
        
        const percentage = health.overall_health || 95;
        healthValue.textContent = `${percentage}%`;
        
        // Update needle rotation (0-180 degrees)
        const rotation = (percentage / 100) * 180;
        healthNeedle.style.transform = `rotate(${rotation}deg)`;
        
        // Update gauge color
        let gaugeColor = '#28a745'; // Green
        if (percentage < 70) gaugeColor = '#dc3545'; // Red
        else if (percentage < 85) gaugeColor = '#ffc107'; // Yellow
        
        healthGauge.style.setProperty('--gauge-color', gaugeColor);
        
        // Update health indicators
        const indicators = this.container.querySelectorAll('.health-dot');
        const healthComponents = health.components || {};
        
        indicators.forEach((dot, index) => {
            const componentNames = ['api', 'database', 'network', 'storage'];
            const componentHealth = healthComponents[componentNames[index]] || 100;
            
            dot.className = 'health-dot ' + 
                (componentHealth >= 90 ? 'active' : 
                 componentHealth >= 70 ? 'warning' : 'error');
        });
    }
    
    updateErrorRate(rateData) {
        const rateNumber = document.getElementById('errorRate');
        const rateSparkline = document.getElementById('rateSparkline');
        
        const currentRate = rateData.current_rate || 0;
        rateNumber.textContent = currentRate.toFixed(1);
        
        // Create sparkline chart
        this.createSparkline(rateSparkline, rateData.historical || []);
    }
    
    updateProgressBars(counts) {
        const totalErrors = Object.values(counts).reduce((sum, count) => sum + count, 0);
        
        Object.keys(counts).forEach(severity => {
            const progressElement = document.getElementById(`${severity}Progress`);
            const percentage = totalErrors > 0 ? (counts[severity] / totalErrors) * 100 : 0;
            
            progressElement.style.width = `${percentage}%`;
            progressElement.style.backgroundColor = this.thresholds[severity].color;
        });
    }
    
    createSparkline(container, data) {
        // Clear existing sparkline
        container.innerHTML = '';
        
        if (!data || data.length === 0) return;
        
        const width = container.offsetWidth;
        const height = container.offsetHeight;
        const maxValue = Math.max(...data);
        const minValue = Math.min(...data);
        const range = maxValue - minValue || 1;
        
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', width);
        svg.setAttribute('height', height);
        svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
        
        // Create path
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        const pathData = data.map((value, index) => {
            const x = (index / (data.length - 1)) * width;
            const y = height - ((value - minValue) / range) * height;
            return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
        }).join(' ');
        
        path.setAttribute('d', pathData);
        path.setAttribute('stroke', '#007bff');
        path.setAttribute('stroke-width', '2');
        path.setAttribute('fill', 'none');
        
        svg.appendChild(path);
        container.appendChild(svg);
    }
    
    onStatusCardClick(cardType) {
        // Handle status card clicks
        switch(cardType) {
            case 'critical-errors':
                showErrorDetails('critical');
                break;
            case 'high-errors':
                showErrorDetails('high');
                break;
            case 'medium-errors':
                showErrorDetails('medium');
                break;
            case 'low-errors':
                showErrorDetails('low');
                break;
            case 'system-health':
                showSystemHealthDetails();
                break;
            case 'error-rate':
                showErrorRateDetails();
                break;
        }
    }
    
    startRealTimeUpdates(interval = 30000) {
        // Start real-time updates every 30 seconds
        this.updateInterval = setInterval(() => {
            this.fetchAndUpdateData();
        }, interval);
    }
    
    stopRealTimeUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
    
    fetchAndUpdateData() {
        // Fetch latest error status data
        fetch('/api/error-status')
            .then(response => response.json())
            .then(data => {
                this.updateIndicators(data);
            })
            .catch(error => {
                console.error('Error fetching status data:', error);
            });
    }
}
```

## 🎨 **Component Styling (CSS)**

### **Comprehensive CSS for All Error Visualization Components**
```css
/* Error Visualization Components Styles */

/* Error Overview Panel */
.error-overview-panel {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    padding: 20px;
    margin-bottom: 20px;
}

.error-overview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    border-bottom: 1px solid #e9ecef;
    padding-bottom: 15px;
}

.error-overview-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 20px;
}

.error-stat-card {
    background: #f8f9fa;
    border-radius: 6px;
    padding: 15px;
    text-align: center;
    transition: transform 0.2s ease;
}

.error-stat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.error-stat-number {
    font-size: 2rem;
    font-weight: bold;
    margin-bottom: 5px;
}

.error-stat-label {
    color: #6c757d;
    font-size: 0.9rem;
}

/* Live Error Feed */
.live-error-feed {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    height: 400px;
    display: flex;
    flex-direction: column;
}

.error-feed-header {
    padding: 15px 20px;
    border-bottom: 1px solid #e9ecef;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.error-feed-controls {
    display: flex;
    gap: 10px;
}

.error-feed-body {
    flex: 1;
    overflow-y: auto;
    padding: 10px;
}

.error-feed-item {
    display: flex;
    align-items: flex-start;
    padding: 10px;
    border-bottom: 1px solid #f1f3f4;
    transition: background-color 0.2s ease;
}

.error-feed-item:hover {
    background-color: #f8f9fa;
}

.error-feed-item.new-error {
    animation: highlightError 2s ease-out;
}

@keyframes highlightError {
    0% { background-color: #fff3cd; }
    100% { background-color: transparent; }
}

.error-severity-indicator {
    width: 4px;
    height: 100%;
    border-radius: 2px;
    margin-right: 12px;
    flex-shrink: 0;
}

.error-severity-indicator.critical { background-color: #dc3545; }
.error-severity-indicator.high { background-color: #fd7e14; }
.error-severity-indicator.medium { background-color: #ffc107; }
.error-severity-indicator.low { background-color: #28a745; }

.error-feed-content {
    flex: 1;
}

.error-feed-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 5px;
}

.error-feed-timestamp {
    color: #6c757d;
    font-size: 0.8rem;
}

.error-feed-message {
    font-size: 0.9rem;
    line-height: 1.4;
    margin-bottom: 5px;
}

.error-feed-details {
    display: flex;
    gap: 15px;
    font-size: 0.8rem;
    color: #6c757d;
}

/* Regional Error Health Map */
.regional-error-map {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    padding: 20px;
}

.map-container {
    position: relative;
    width: 100%;
    height: 400px;
    border: 1px solid #e9ecef;
    border-radius: 6px;
    overflow: hidden;
}

.region-tooltip {
    position: absolute;
    background: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 12px;
    pointer-events: none;
    z-index: 1000;
}

/* Error Trends Chart */
.error-trends-container {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    padding: 20px;
}

.chart-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.time-range-selector {
    display: flex;
    gap: 5px;
}

.time-range-btn {
    padding: 5px 12px;
    border: 1px solid #dee2e6;
    background: #fff;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.time-range-btn.active {
    background: #007bff;
    color: white;
    border-color: #007bff;
}

/* Error Metrics Table */
.error-table-container {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    overflow: hidden;
}

.table-controls {
    padding: 15px 20px;
    background: #f8f9fa;
    border-bottom: 1px solid #e9ecef;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 15px;
}

.table-search {
    flex: 1;
    min-width: 200px;
}

.table-filters {
    display: flex;
    gap: 10px;
}

.table-actions {
    display: flex;
    gap: 10px;
}

.table-responsive {
    max-height: 600px;
    overflow-y: auto;
}

.error-message {
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.severity-critical { background-color: #dc3545; }
.severity-high { background-color: #fd7e14; }
.severity-medium { background-color: #ffc107; }
.severity-low { background-color: #28a745; }

.retry-count {
    font-size: 0.8rem;
}

.table-footer {
    padding: 15px 20px;
    background: #f8f9fa;
    border-top: 1px solid #e9ecef;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* Error Status Indicators */
.error-status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
    margin-bottom: 20px;
}

.status-card {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    padding: 20px;
    cursor: pointer;
    transition: all 0.2s ease;
    border-left: 4px solid transparent;
}

.status-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.status-card.critical-errors { border-left-color: #dc3545; }
.status-card.high-errors { border-left-color: #fd7e14; }
.status-card.medium-errors { border-left-color: #ffc107; }
.status-card.low-errors { border-left-color: #28a745; }
.status-card.system-health { border-left-color: #17a2b8; }
.status-card.error-rate { border-left-color: #6f42c1; }

.status-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
}

.status-header h5 {
    margin: 0;
    font-size: 1rem;
    color: #495057;
}

.status-header i {
    font-size: 1.2rem;
    color: #6c757d;
}

.status-body {
    margin-bottom: 15px;
}

.status-number {
    font-size: 2.5rem;
    font-weight: bold;
    line-height: 1;
    margin-bottom: 5px;
}

.status-trend {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.9rem;
    margin-bottom: 5px;
}

.status-trend.trend-up { color: #dc3545; }
.status-trend.trend-down { color: #28a745; }
.status-trend.trend-neutral { color: #6c757d; }

.status-description {
    color: #6c757d;
    font-size: 0.8rem;
}

.status-footer {
    border-top: 1px solid #e9ecef;
    padding-top: 10px;
}

.status-bar {
    width: 100%;
    height: 4px;
    background: #e9ecef;
    border-radius: 2px;
    overflow: hidden;
}

.status-progress {
    height: 100%;
    transition: width 0.3s ease;
}

/* Health Gauge */
.health-gauge {
    position: relative;
    width: 120px;
    height: 60px;
    margin: 0 auto 10px;
    --gauge-color: #28a745;
}

.health-gauge::before {
    content: '';
    position: absolute;
    width: 120px;
    height: 60px;
    border: 8px solid #e9ecef;
    border-bottom: none;
    border-radius: 120px 120px 0 0;
    box-sizing: border-box;
}

.health-gauge::after {
    content: '';
    position: absolute;
    width: 120px;
    height: 60px;
    border: 8px solid var(--gauge-color);
    border-bottom: none;
    border-radius: 120px 120px 0 0;
    box-sizing: border-box;
    clip-path: polygon(0 0, 50% 0, 50% 100%, 0 100%);
}

.gauge-needle {
    position: absolute;
    top: 50px;
    left: 56px;
    width: 2px;
    height: 40px;
    background: #333;
    transform-origin: bottom center;
    transition: transform 0.5s ease;
}

.gauge-value {
    position: absolute;
    bottom: -5px;
    left: 50%;
    transform: translateX(-50%);
    font-weight: bold;
    font-size: 1.1rem;
}

.health-indicators {
    display: flex;
    justify-content: center;
    gap: 8px;
    margin-top: 10px;
}

.health-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #e9ecef;
    transition: background-color 0.3s ease;
}

.health-dot.active { background: #28a745; }
.health-dot.warning { background: #ffc107; }
.health-dot.error { background: #dc3545; }

/* Error Rate Display */
.rate-display {
    text-align: center;
    margin-bottom: 10px;
}

.rate-number {
    font-size: 2rem;
    font-weight: bold;
    color: #007bff;
}

.rate-unit {
    font-size: 0.9rem;
    color: #6c757d;
    margin-left: 5px;
}

.rate-sparkline {
    height: 40px;
    margin-bottom: 10px;
}

.rate-threshold {
    text-align: center;
}

.threshold-label {
    font-size: 0.8rem;
    color: #6c757d;
}

/* Timeline Visualization */
.timeline-tooltip {
    position: absolute;
    background: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 10px;
    border-radius: 5px;
    font-size: 12px;
    pointer-events: none;
    z-index: 1000;
}

.correlation-tooltip {
    position: absolute;
    background: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 10px;
    border-radius: 5px;
    font-size: 12px;
    pointer-events: none;
    z-index: 1000;
}

/* Responsive Design */
@media (max-width: 768px) {
    .error-status-grid {
        grid-template-columns: 1fr;
    }
    
    .table-controls {
        flex-direction: column;
        align-items: stretch;
    }
    
    .table-filters {
        justify-content: stretch;
    }
    
    .table-filters select {
        flex: 1;
    }
    
    .chart-controls {
        flex-direction: column;
        gap: 15px;
    }
    
    .time-range-selector {
        justify-content: center;
        flex-wrap: wrap;
    }
}

/* Animation Classes */
.fade-in {
    animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.pulse {
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}

/* Loading States */
.loading-spinner {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 3px solid #f3f3f3;
    border-top: 3px solid #007bff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Print Styles */
@media print {
    .error-status-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    
    .status-card {
        break-inside: avoid;
        box-shadow: none;
        border: 1px solid #ccc;
    }
    
    .error-table-container {
        box-shadow: none;
        border: 1px solid #ccc;
    }
    
    .table-controls,
    .table-footer {
        display: none;
    }
}
```

## 🔧 **Integration Code**

### **Main Error Dashboard Integration**
```javascript
// Main Error Dashboard Integration
class ErrorDashboard {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            refreshInterval: 30000, // 30 seconds
            enableRealTime: true,
            enableNotifications: true,
            ...options
        };
        
        this.components = {};
        this.isInitialized = false;
        
        this.init();
    }
    
    async init() {
        try {
            // Create dashboard structure
            this.createDashboardStructure();
            
            // Initialize all components
            await this.initializeComponents();
            
            // Start real-time updates
            if (this.options.enableRealTime) {
                this.startRealTimeUpdates();
            }
            
            // Setup event listeners
            this.setupEventListeners();
            
            this.isInitialized = true;
            console.log('Error Dashboard initialized successfully');
            
        } catch (error) {
            console.error('Error initializing dashboard:', error);
            this.showErrorMessage('Failed to initialize error dashboard');
        }
    }
    
    createDashboardStructure() {
        this.container.innerHTML = `
            <div class="error-dashboard">
                <div class="dashboard-header">
                    <h2>Error Tracking Dashboard</h2>
                    <div class="dashboard-controls">
                        <button id="refreshDashboard" class="btn btn-outline-primary">
                            <i class="fas fa-sync-alt"></i> Refresh
                        </button>
                        <button id="exportErrors" class="btn btn-outline-secondary">
                            <i class="fas fa-download"></i> Export
                        </button>
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" id="realTimeToggle" checked>
                            <label class="form-check-label" for="realTimeToggle">
                                Real-time Updates
                            </label>
                        </div>
                    </div>
                </div>
                
                <!-- Error Status Indicators -->
                <div class="dashboard-section">
                    <div id="errorStatusIndicators"></div>
                </div>
                
                <!-- Error Overview and Live Feed -->
                <div class="dashboard-row">
                    <div class="dashboard-col-8">
                        <div class="dashboard-section">
                            <div id="errorOverviewPanel"></div>
                        </div>
                    </div>
                    <div class="dashboard-col-4">
                        <div class="dashboard-section">
                            <div id="liveErrorFeed"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Charts Row -->
                <div class="dashboard-row">
                    <div class="dashboard-col-6">
                        <div class="dashboard-section">
                            <div id="errorTrendsChart"></div>
                        </div>
                    </div>
                    <div class="dashboard-col-6">
                        <div class="dashboard-section">
                            <div id="errorDistributionChart"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Regional Map and Timeline -->
                <div class="dashboard-row">
                    <div class="dashboard-col-8">
                        <div class="dashboard-section">
                            <div id="regionalErrorMap"></div>
                        </div>
                    </div>
                    <div class="dashboard-col-4">
                        <div class="dashboard-section">
                            <div id="errorRateGauge"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Timeline and Correlation -->
                <div class="dashboard-row">
                    <div class="dashboard-col-12">
                        <div class="dashboard-section">
                            <div id="errorTimelineVisualization"></div>
                        </div>
                    </div>
                </div>
                
                <div class="dashboard-row">
                    <div class="dashboard-col-6">
                        <div class="dashboard-section">
                            <div id="errorCorrelationMatrix"></div>
                        </div>
                    </div>
                    <div class="dashboard-col-6">
                        <div class="dashboard-section">
                            <div id="errorMetricsTable"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    async initializeComponents() {
        // Initialize all error visualization components
        this.components.statusIndicators = new ErrorStatusIndicators('errorStatusIndicators');
        this.components.overviewPanel = new ErrorOverviewPanel('errorOverviewPanel');
        this.components.liveFeed = new LiveErrorFeed('liveErrorFeed');
        this.components.trendsChart = new ErrorTrendsChart('errorTrendsChart');
        this.components.distributionChart = new ErrorDistributionChart('errorDistributionChart');
        this.components.regionalMap = new RegionalErrorHeatmap('regionalErrorMap');
        this.components.rateGauge = new ErrorRateGauge('errorRateGauge');
        this.components.timeline = new ErrorTimelineVisualization('errorTimelineVisualization');
        this.components.correlationMatrix = new ErrorCorrelationMatrix('errorCorrelationMatrix');
        this.components.metricsTable = new ErrorMetricsTable('errorMetricsTable');
        
        // Load initial data for all components
        await this.loadAllData();
    }
    
    async loadAllData() {
        try {
            // Fetch all error data from API
            const [
                statusData,
                overviewData,
                trendsData,
                distributionData,
                regionalData,
                timelineData,
                correlationData,
                metricsData
            ] = await Promise.all([
                this.fetchErrorStatus(),
                this.fetchErrorOverview(),
                this.fetchErrorTrends(),
                this.fetchErrorDistribution(),
                this.fetchRegionalErrors(),
                this.fetchErrorTimeline(),
                this.fetchErrorCorrelations(),
                this.fetchErrorMetrics()
            ]);
            
            // Update all components with data
            this.components.statusIndicators.updateIndicators(statusData);
            this.components.overviewPanel.updateOverview(overviewData);
            this.components.trendsChart.updateChart(trendsData);
            this.components.distributionChart.updateChart(distributionData);
            this.components.regionalMap.updateMap(regionalData);
            this.components.timeline.update(timelineData);
            this.components.correlationMatrix.update(correlationData);
            this.components.metricsTable.loadData(metricsData);
            
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showErrorMessage('Failed to load error data');
        }
    }
    
    setupEventListeners() {
        // Refresh button
        document.getElementById('refreshDashboard').addEventListener('click', () => {
            this.refreshDashboard();
        });
        
        // Export button
        document.getElementById('exportErrors').addEventListener('click', () => {
            this.exportErrorData();
        });
        
        // Real-time toggle
        document.getElementById('realTimeToggle').addEventListener('change', (e) => {
            if (e.target.checked) {
                this.startRealTimeUpdates();
            } else {
                this.stopRealTimeUpdates();
            }
        });
        
        // Component-specific event listeners
        this.setupComponentEventListeners();
    }
    
    setupComponentEventListeners() {
        // Listen for component interactions
        document.addEventListener('errorSelected', (e) => {
            this.handleErrorSelection(e.detail);
        });
        
        document.addEventListener('regionSelected', (e) => {
            this.handleRegionSelection(e.detail);
        });
        
        document.addEventListener('timeRangeChanged', (e) => {
            this.handleTimeRangeChange(e.detail);
        });
    }
    
    startRealTimeUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        this.updateInterval = setInterval(() => {
            this.refreshDashboard();
        }, this.options.refreshInterval);
        
        // Start real-time updates for individual components
        Object.values(this.components).forEach(component => {
            if (component.startRealTimeUpdates) {
                component.startRealTimeUpdates();
            }
        });
    }
    
    stopRealTimeUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        
        // Stop real-time updates for individual components
        Object.values(this.components).forEach(component => {
            if (component.stopRealTimeUpdates) {
                component.stopRealTimeUpdates();
            }
        });
    }
    
    async refreshDashboard() {
        try {
            // Show loading indicator
            this.showLoadingIndicator();
            
            // Reload all data
            await this.loadAllData();
            
            // Hide loading indicator
            this.hideLoadingIndicator();
            
            // Show success message
            this.showSuccessMessage('Dashboard refreshed successfully');
            
        } catch (error) {
            console.error('Error refreshing dashboard:', error);
            this.hideLoadingIndicator();
            this.showErrorMessage('Failed to refresh dashboard');
        }
    }
    
    async exportErrorData() {
        try {
            const errorData = await this.fetchErrorMetrics();
            const csv = this.convertToCSV(errorData);
            this.downloadCSV(csv, `error-report-${new Date().toISOString().split('T')[0]}.csv`);
            
            this.showSuccessMessage('Error data exported successfully');
            
        } catch (error) {
            console.error('Error exporting data:', error);
            this.showErrorMessage('Failed to export error data');
        }
    }
    
    // API Methods
    async fetchErrorStatus() {
        const response = await fetch('/api/error-status');
        if (!response.ok) throw new Error('Failed to fetch error status');
        return response.json();
    }
    
    async fetchErrorOverview() {
        const response = await fetch('/api/error-overview');
        if (!response.ok) throw new Error('Failed to fetch error overview');
        return response.json();
    }
    
    async fetchErrorTrends() {
        const response = await fetch('/api/error-trends');
        if (!response.ok) throw new Error('Failed to fetch error trends');
        return response.json();
    }
    
    async fetchErrorDistribution() {
        const response = await fetch('/api/error-distribution');
        if (!response.ok) throw new Error('Failed to fetch error distribution');
        return response.json();
    }
    
    async fetchRegionalErrors() {
        const response = await fetch('/api/regional-errors');
        if (!response.ok) throw new Error('Failed to fetch regional errors');
        return response.json();
    }
    
    async fetchErrorTimeline() {
        const response = await fetch('/api/error-timeline');
        if (!response.ok) throw new Error('Failed to fetch error timeline');
        return response.json();
    }
    
    async fetchErrorCorrelations() {
        const response = await fetch('/api/error-correlations');
        if (!response.ok) throw new Error('Failed to fetch error correlations');
        return response.json();
    }
    
    async fetchErrorMetrics() {
        const response = await fetch('/api/error-metrics');
        if (!response.ok) throw new Error('Failed to fetch error metrics');
        return response.json();
    }
    
    // Event Handlers
    handleErrorSelection(errorData) {
        // Highlight related errors across all components
        Object.values(this.components).forEach(component => {
            if (component.highlightError) {
                component.highlightError(errorData.error_id);
            }
        });
        
        // Show error details modal
        this.showErrorDetailsModal(errorData);
    }
    
    handleRegionSelection(regionData) {
        // Filter all components by selected region
        Object.values(this.components).forEach(component => {
            if (component.filterByRegion) {
                component.filterByRegion(regionData.region);
            }
        });
    }
    
    handleTimeRangeChange(timeRange) {
        // Update all time-sensitive components
        Object.values(this.components).forEach(component => {
            if (component.updateTimeRange) {
                component.updateTimeRange(timeRange);
            }
        });
    }
    
    // Utility Methods
    convertToCSV(data) {
        const headers = Object.keys(data[0] || {});
        const csvContent = [
            headers.join(','),
            ...data.map(row => headers.map(header => 
                `"${String(row[header] || '').replace(/"/g, '""')}"`
            ).join(','))
        ].join('\n');
        
        return csvContent;
    }
    
    downloadCSV(csv, filename) {
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }
    
    showLoadingIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'dashboardLoading';
        indicator.className = 'loading-overlay';
        indicator.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner"></div>
                <p>Loading dashboard data...</p>
            </div>
        `;
        this.container.appendChild(indicator);
    }
    
    hideLoadingIndicator() {
        const indicator = document.getElementById('dashboardLoading');
        if (indicator) {
            indicator.remove();
        }
    }
    
    showSuccessMessage(message) {
        this.showToast(message, 'success');
    }
    
    showErrorMessage(message) {
        this.showToast(message, 'error');
    }
    
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Hide toast after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    showErrorDetailsModal(errorData) {
        // Create and show error details modal
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Error Details</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="error-details">
                            <div class="row">
                                <div class="col-md-6">
                                    <strong>Error ID:</strong> ${errorData.error_id}<br>
                                    <strong>Timestamp:</strong> ${new Date(errorData.timestamp).toLocaleString()}<br>
                                    <strong>Severity:</strong> <span class="badge severity-${errorData.severity}">${errorData.severity}</span><br>
                                    <strong>Type:</strong> ${errorData.error_type}<br>
                                    <strong>Region:</strong> ${errorData.region || 'N/A'}
                                </div>
                                <div class="col-md-6">
                                    <strong>Request ID:</strong> ${errorData.request_id}<br>
                                    <strong>Retry Count:</strong> ${errorData.retry_count}/${errorData.max_retries}<br>
                                    <strong>Status:</strong> ${errorData.resolution_status || 'Unresolved'}<br>
                                    <strong>Impact Score:</strong> ${errorData.impact_score}/10
                                </div>
                            </div>
                            <div class="mt-3">
                                <strong>Error Message:</strong>
                                <pre class="error-message-pre">${errorData.message}</pre>
                            </div>
                            ${errorData.stack_trace ? `
                                <div class="mt-3">
                                    <strong>Stack Trace:</strong>
                                    <pre class="stack-trace-pre">${errorData.stack_trace}</pre>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" onclick="retryError('${errorData.error_id}')">Retry</button>
                        <button type="button" class="btn btn-success" onclick="resolveError('${errorData.error_id}')">Mark Resolved</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
        
        // Clean up modal when hidden
        modal.addEventListener('hidden.bs.modal', () => {
            modal.remove();
        });
    }
    
    destroy() {
        // Stop real-time updates
        this.stopRealTimeUpdates();
        
        // Destroy all components
        Object.values(this.components).forEach(component => {
            if (component.destroy) {
                component.destroy();
            }
        });
        
        // Clear container
        this.container.innerHTML = '';
        
        this.isInitialized = false;
    }
}

// Global error handling functions
window.retryError = async function(errorId) {
    try {
        const response = await fetch(`/api/retry-error/${errorId}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showToast('Error retry initiated successfully', 'success');
            // Refresh dashboard
            if (window.errorDashboard) {
                window.errorDashboard.refreshDashboard();
            }
        } else {
            throw new Error('Failed to retry error');
        }
    } catch (error) {
        console.error('Error retrying:', error);
        showToast('Failed to retry error', 'error');
    }
};

window.resolveError = async function(errorId) {
    try {
        const response = await fetch(`/api/resolve-error/${errorId}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showToast('Error marked as resolved', 'success');
            // Refresh dashboard
            if (window.errorDashboard) {
                window.errorDashboard.refreshDashboard();
            }
        } else {
            throw new Error('Failed to resolve error');
        }
    } catch (error) {
        console.error('Error resolving:', error);
        showToast('Failed to resolve error', 'error');
    }
};

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize error dashboard if container exists
    const dashboardContainer = document.getElementById('errorDashboard');
    if (dashboardContainer) {
        window.errorDashboard = new ErrorDashboard('errorDashboard', {
            refreshInterval: 30000,
            enableRealTime: true,
            enableNotifications: true
        });
    }
});
```

## 📋 **Implementation Checklist**

### **Component Implementation Status**
- ✅ **Error Overview Panel** - Complete with stats cards and summary metrics
- ✅ **Live Error Feed** - Real-time streaming with filtering and severity indicators
- ✅ **Regional Error Health Map** - D3.js heatmap with interactive tooltips
- ✅ **Error Trends Chart** - Chart.js line chart with multiple datasets
- ✅ **Error Distribution Chart** - Chart.js donut chart with custom center plugin
- ✅ **Error Rate Gauge** - D3.js gauge with animated needle and color coding
- ✅ **Error Timeline Visualization** - D3.js timeline with brushing and zooming
- ✅ **Error Correlation Matrix** - D3.js matrix with correlation coefficients
- ✅ **Error Metrics Table** - Advanced data table with sorting, filtering, and export
- ✅ **Error Status Indicators** - Real-time status cards with health metrics

### **Integration Features**
- ✅ **Real-time Updates** - WebSocket integration for live data streaming
- ✅ **Cross-component Communication** - Event-driven architecture for component interaction
- ✅ **Data Export** - CSV export functionality for all error data
- ✅ **Responsive Design** - Mobile-friendly layouts with Bootstrap integration
- ✅ **Accessibility** - ARIA attributes and keyboard navigation support
- ✅ **Error Handling** - Comprehensive error handling with user feedback
- ✅ **Performance Optimization** - Efficient data loading and rendering
- ✅ **Customization** - Configurable options for refresh intervals and features

### **API Integration Points**
- ✅ **Error Status API** - `/api/error-status` for real-time status indicators
- ✅ **Error Overview API** - `/api/error-overview` for summary statistics
- ✅ **Error Trends API** - `/api/error-trends` for historical trend data
- ✅ **Error Distribution API** - `/api/error-distribution` for severity breakdown
- ✅ **Regional Errors API** - `/api/regional-errors` for geographic error data
- ✅ **Error Timeline API** - `/api/error-timeline` for chronological error events
- ✅ **Error Correlations API** - `/api/error-correlations` for pattern analysis
- ✅ **Error Metrics API** - `/api/error-metrics` for detailed error records

### **Visual Design Elements**
- ✅ **Color Coding** - Consistent severity-based color scheme
- ✅ **Interactive Elements** - Hover effects, click handlers, and tooltips
- ✅ **Loading States** - Spinners and progress indicators
- ✅ **Animation** - Smooth transitions and data updates
- ✅ **Typography** - Clear hierarchy and readable fonts
- ✅ **Icons** - FontAwesome icons for visual clarity
- ✅ **Layout** - Grid-based responsive layout system
- ✅ **Theming** - Bootstrap-compatible styling

---

## 🎯 **Summary**

This comprehensive error visualization components specification provides:

1. **8 Advanced Visualization Components** - Each with detailed implementation code, interactive features, and real-time capabilities

2. **Complete Integration Framework** - Main dashboard class that orchestrates all components with event-driven communication

3. **Production-Ready Code** - Includes error handling, performance optimization, accessibility features, and responsive design

4. **API Integration** - Comprehensive API endpoints for all error tracking data with proper error handling

5. **Advanced Features** - Real-time updates, data export, cross-component filtering, and interactive error management

6. **Comprehensive Styling** - Complete CSS with responsive design, animations, and print styles

The components are designed to integrate seamlessly with the existing [`ErrorDashboardAPI`](src/python/automation/error_dashboard_api.py) infrastructure and provide a sophisticated, user-friendly interface for comprehensive error tracking and management in the CarbonCast RDA automation system.