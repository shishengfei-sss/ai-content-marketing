// assets/charts.js
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  // --- 模块覆盖分布 ---
  var chart1 = echarts.init(document.getElementById('chart-coverage'), null, { renderer: 'svg' });
  chart1.setOption({
    animation: false,
    tooltip: { trigger: 'axis', appendToBody: true },
    grid: { top: 20, right: 20, bottom: 50, left: 140 },
    xAxis: { type: 'value', max: 15, axisLabel: { color: muted }, splitLine: { lineStyle: { color: rule } } },
    yAxis: { type: 'category', data: [
      'H5移动端', '性能测试', '回归测试', '数据权限', '平台管理',
      '系统设置', '产品/任务/活动', '合同/订单', '报价', '商机',
      '客户', '线索', '内容/Agent', '安全测试', 'CRM API', '认证API'
    ], axisLabel: { color: ink, fontSize: 12 } },
    series: [{
      type: 'bar',
      data: [11, 4, 15, 6, 8, 13, 20, 13, 8, 11, 5, 5, 7, 5, 6, 5],
      itemStyle: { color: accent, borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: ink, fontSize: 11 }
    }]
  });
  window.addEventListener('resize', function() { chart1.resize(); });

  // --- 测试分层占比 ---
  var chart2 = echarts.init(document.getElementById('chart-pie'), null, { renderer: 'svg' });
  chart2.setOption({
    animation: false,
    tooltip: { trigger: 'item', appendToBody: true },
    legend: { bottom: 0, textStyle: { color: muted } },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: bg2, borderWidth: 2 },
      label: { color: ink, fontSize: 12, formatter: '{b}\n{d}%' },
      data: [
        { value: 43, name: 'CRM核心模块', itemStyle: { color: accent } },
        { value: 27, name: '后端API', itemStyle: { color: accent2 } },
        { value: 42, name: '设置/管理/权限', itemStyle: { color: muted } },
        { value: 15, name: '回归测试', itemStyle: { color: '#4CAF50' } },
        { value: 4, name: '性能测试', itemStyle: { color: '#FF9800' } },
        { value: 11, name: 'H5移动端', itemStyle: { color: '#9C27B0' } }
      ]
    }]
  });
  window.addEventListener('resize', function() { chart2.resize(); });

  // --- 通过率仪表盘 ---
  var chart3 = echarts.init(document.getElementById('chart-gauge'), null, { renderer: 'svg' });
  chart3.setOption({
    animation: false,
    series: [{
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: 100,
      splitNumber: 10,
      radius: '90%',
      center: ['50%', '55%'],
      axisLine: { lineStyle: { width: 20, color: [[0.7, '#FF9800'], [0.9, '#4CAF50'], [1, accent]] } },
      axisTick: { length: 8, lineStyle: { color: 'auto' } },
      splitLine: { length: 15, lineStyle: { color: 'auto', width: 2 } },
      axisLabel: { color: muted, fontSize: 11, distance: 25 },
      pointer: { width: 4, length: '60%', itemStyle: { color: ink } },
      detail: { formatter: '{value}%', fontSize: 36, fontWeight: 700, color: ink, offsetCenter: [0, '30%'] },
      data: [{ value: 100 }]
    }]
  });
  window.addEventListener('resize', function() { chart3.resize(); });
})();
