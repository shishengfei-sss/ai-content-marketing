(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var hard = style.getPropertyValue('--hard').trim();
  var pass = style.getPropertyValue('--pass').trim();

  // --- Chart 1: Rounds Distribution (Pie) ---
  var chartRounds = echarts.init(document.getElementById('chart-rounds'), null, { renderer: 'svg' });
  chartRounds.setOption({
    animation: false,
    tooltip: {
      trigger: 'item',
      appendToBody: true,
      formatter: '{b}: {c} 用例 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: ink, fontSize: 13 },
      itemGap: 12
    },
    color: [accent, accent2, '#8b5cf6', '#f59e0b', '#10b981', '#ef4444', '#6366f1'],
    series: [{
      name: '测试用例分布',
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['38%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 6,
        borderColor: bg2,
        borderWidth: 2
      },
      label: {
        show: true,
        formatter: '{b}\n{c} 用例',
        fontSize: 12,
        color: ink
      },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' }
      },
      data: [
        { value: 375, name: 'Round 1 后端 API' },
        { value: 30, name: 'Round 2 Web UI' },
        { value: 20, name: 'Round 3 小程序 UI' },
        { value: 30, name: 'Round 4 E2E 集成' },
        { value: 25, name: 'Round 5 Mock 对接' },
        { value: 30, name: 'Round 6 安全/PII' },
        { value: 10, name: 'Round 7 回归' }
      ]
    }]
  });
  window.addEventListener('resize', function() { chartRounds.resize(); });

  // --- Chart 2: Milestones Stacked Bar ---
  var chartMilestones = echarts.init(document.getElementById('chart-milestones'), null, { renderer: 'svg' });
  chartMilestones.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true
    },
    legend: {
      data: ['主用例', '边界值变体', '业务场景'],
      top: 0,
      textStyle: { color: ink, fontSize: 13 },
      itemGap: 20
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: 50, containLabel: true },
    xAxis: {
      type: 'category',
      data: ['M0 权限', 'M1 套餐', 'M2 状态', 'M4 商品', 'M5 订单', 'M3 支付', 'M6 核销', 'M7 公域'],
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted, fontSize: 12, interval: 0 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '测试点数量',
      nameTextStyle: { color: muted, fontSize: 12 },
      axisLine: { show: false },
      axisLabel: { color: muted, fontSize: 12 },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    color: [accent, accent2, pass],
    series: [
      {
        name: '主用例',
        type: 'bar',
        stack: 'total',
        emphasis: { focus: 'series' },
        data: [60, 35, 40, 50, 60, 45, 45, 40],
        barWidth: '50%',
        itemStyle: { borderRadius: [0, 0, 0, 0] }
      },
      {
        name: '边界值变体',
        type: 'bar',
        stack: 'total',
        emphasis: { focus: 'series' },
        data: [250, 130, 150, 200, 204, 210, 200, 200]
      },
      {
        name: '业务场景',
        type: 'bar',
        stack: 'total',
        emphasis: { focus: 'series' },
        data: [130, 80, 120, 120, 118, 140, 130, 160],
        itemStyle: { borderRadius: [4, 4, 0, 0] }
      }
    ]
  });
  window.addEventListener('resize', function() { chartMilestones.resize(); });

})();
