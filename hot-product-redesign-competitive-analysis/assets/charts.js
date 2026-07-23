(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var bg3 = style.getPropertyValue('--bg3').trim();

  // Common chart options
  var commonOption = {
    backgroundColor: 'transparent',
    textStyle: {
      color: ink,
      fontFamily: 'InstrumentSans, sans-serif'
    },
    animation: false
  };

  // --- Chart 1: Positioning Scatter Chart ---
  var chart1 = echarts.init(document.getElementById('chart-positioning'), null, { renderer: 'svg' });
  
  var positioningData = [
    // [创新程度, 迭代速度(天), 名称, 气泡大小, 赛道]
    [2, 1, '华强北白牌', 70, '硬件'],
    [3, 7, '绿联/倍思', 55, '硬件'],
    [4, 180, '小米生态链', 85, '硬件'],
    [5, 90, '安克创新', 75, '硬件'],
    [3, 1, 'SHEIN', 90, '快时尚'],
    [2.5, 3, 'Temu卖家', 85, '快时尚'],
    [4, 7, 'Cider', 50, '快时尚'],
    [2, 1, 'Indie Hacker', 45, 'SaaS'],
    [4, 30, '垂直SaaS', 60, 'SaaS'],
    [5, 90, '大厂复刻', 80, 'SaaS'],
    [5, 180, '开源复刻', 65, 'SaaS'],
    [4.5, 60, '飞书/钉钉', 75, 'SaaS']
  ];

  var categoryColors = {
    '硬件': accent,
    '快时尚': accent2,
    'SaaS': '#f59e0b'
  };

  var seriesData = {};
  positioningData.forEach(function(item) {
    var cat = item[4];
    if (!seriesData[cat]) {
      seriesData[cat] = [];
    }
    seriesData[cat].push({
      value: [item[0], item[1]],
      name: item[2],
      symbolSize: item[3] * 0.4
    });
  });

  var series = [];
  Object.keys(seriesData).forEach(function(cat, idx) {
    series.push({
      name: cat,
      type: 'scatter',
      data: seriesData[cat],
      itemStyle: {
        color: categoryColors[cat],
        opacity: 0.7,
        borderColor: categoryColors[cat],
        borderWidth: 2
      },
      emphasis: {
        itemStyle: {
          opacity: 1,
          shadowBlur: 10,
          shadowColor: categoryColors[cat]
        },
        label: {
          show: true,
          formatter: function(params) {
            return params.name;
          },
          position: 'top',
          color: ink,
          fontSize: 11,
          fontWeight: 600
        }
      },
      label: {
        show: true,
        formatter: function(params) {
          return params.name;
        },
        position: 'top',
        color: ink,
        fontSize: 10
      }
    });
  });

  chart1.setOption({
    ...commonOption,
    tooltip: {
      trigger: 'item',
      backgroundColor: bg2,
      borderColor: rule,
      textStyle: { color: ink },
      formatter: function(params) {
        return '<strong>' + params.name + '</strong><br/>' +
               '创新程度：' + params.value[0] + '/10<br/>' +
               '迭代速度：' + (params.value[1] < 1 ? '极快' : params.value[1] + '天') + '<br/>' +
               '赛道：' + params.seriesName;
      }
    },
    legend: {
      data: Object.keys(seriesData),
      textStyle: { color: muted },
      top: 10,
      right: 20
    },
    grid: {
      left: '8%',
      right: '5%',
      bottom: '12%',
      top: '15%'
    },
    xAxis: {
      name: '创新程度 →',
      nameTextStyle: { color: muted, padding: [10, 0, 0, 0] },
      type: 'value',
      min: 0,
      max: 10,
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    yAxis: {
      name: '迭代速度（天）',
      nameTextStyle: { color: muted, padding: [0, 0, 10, 0] },
      type: 'log',
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { 
        color: muted,
        formatter: function(val) {
          if (val < 1) return '极快';
          return val + '天';
        }
      },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } },
      inverse: false
    },
    series: series
  });
  window.addEventListener('resize', function() { chart1.resize(); });

  // --- Chart 2: Radar Chart - Cross-Track Comparison ---
  var chart2 = echarts.init(document.getElementById('chart-radar'), null, { renderer: 'svg' });
  
  chart2.setOption({
    ...commonOption,
    tooltip: {
      backgroundColor: bg2,
      borderColor: rule,
      textStyle: { color: ink }
    },
    legend: {
      data: ['快时尚/跨境电商', '消费电子/硬件', 'SaaS/软件'],
      textStyle: { color: muted },
      top: 10
    },
    radar: {
      indicator: [
        { name: '进入门槛', max: 10 },
        { name: '迭代速度', max: 10 },
        { name: '盈利潜力', max: 10 },
        { name: '竞争烈度', max: 10 },
        { name: 'IP风险', max: 10 },
        { name: '规模化潜力', max: 10 }
      ],
      axisName: {
        color: ink,
        fontSize: 12,
        fontWeight: 600
      },
      splitLine: {
        lineStyle: { color: rule }
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(99,102,241,0.02)', 'rgba(99,102,241,0.05)']
        }
      },
      axisLine: {
        lineStyle: { color: rule }
      }
    },
    series: [{
      type: 'radar',
      data: [
        {
          value: [3, 9.5, 9, 9, 8, 9.5],
          name: '快时尚/跨境电商',
          lineStyle: { color: accent2, width: 2 },
          areaStyle: { color: 'rgba(34,211,238,0.15)' },
          itemStyle: { color: accent2 }
        },
        {
          value: [5, 6, 7.5, 7.5, 6, 8.5],
          name: '消费电子/硬件',
          lineStyle: { color: accent, width: 2 },
          areaStyle: { color: 'rgba(99,102,241,0.15)' },
          itemStyle: { color: accent }
        },
        {
          value: [4, 8.5, 8, 8, 5, 8],
          name: 'SaaS/软件',
          lineStyle: { color: '#f59e0b', width: 2 },
          areaStyle: { color: 'rgba(245,158,11,0.15)' },
          itemStyle: { color: '#f59e0b' }
        }
      ]
    }]
  });
  window.addEventListener('resize', function() { chart2.resize(); });

  // --- Chart 3: Porter's Five Forces Bar Chart ---
  var chart3 = echarts.init(document.getElementById('chart-forces'), null, { renderer: 'svg' });
  
  chart3.setOption({
    ...commonOption,
    tooltip: {
      trigger: 'axis',
      backgroundColor: bg2,
      borderColor: rule,
      textStyle: { color: ink },
      axisPointer: { type: 'shadow' }
    },
    grid: {
      left: '3%',
      right: '8%',
      bottom: '3%',
      top: '5%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      max: 10,
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { 
        color: muted,
        formatter: function(val) {
          if (val === 0) return '弱';
          if (val === 5) return '中';
          if (val === 10) return '强';
          return val;
        }
      },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    yAxis: {
      type: 'category',
      data: ['供应商议价能力', '新进入者威胁', '替代品威胁', '买方议价能力', '行业竞争'],
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: ink, fontSize: 13, fontWeight: 500 }
    },
    series: [{
      type: 'bar',
      data: [
        { value: 3, itemStyle: { color: '#10b981' } },
        { value: 6, itemStyle: { color: '#f59e0b' } },
        { value: 5, itemStyle: { color: '#f59e0b' } },
        { value: 8.5, itemStyle: { color: '#ef4444' } },
        { value: 9, itemStyle: { color: '#ef4444' } }
      ],
      barWidth: '50%',
      label: {
        show: true,
        position: 'right',
        color: ink,
        fontWeight: 600,
        formatter: function(params) {
          var labels = ['弱', '较弱', '中', '较强', '强'];
          var idx = Math.floor(params.value / 2.5);
          if (idx > 4) idx = 4;
          return labels[idx];
        }
      }
    }]
  });
  window.addEventListener('resize', function() { chart3.resize(); });

})();
