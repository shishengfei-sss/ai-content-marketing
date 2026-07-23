(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var fail = style.getPropertyValue('--fail').trim();
  var warn = style.getPropertyValue('--warn').trim();
  var skip = style.getPropertyValue('--skip').trim();

  // Chart 1: Pass Rate by Module
  var chart1 = echarts.init(document.getElementById('chart-pass-rate'), null, { renderer: 'svg' });
  chart1.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true,
      formatter: function(p) {
        return p[0].name + '<br/>通过率: <b>' + p[0].value + '%</b><br/>通过/总数: ' + p[0].data.pass + '/' + p[0].data.total;
      }
    },
    grid: { left: 100, right: 40, top: 20, bottom: 40 },
    xAxis: {
      type: 'value', max: 100,
      axisLabel: { formatter: '{value}%', color: muted, fontSize: 11 },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    yAxis: {
      type: 'category',
      data: ['M8 UAT', 'M0 额度', 'M1 多租户', '1d 人格', 'bd 边界', 'pl Persona', '0a 文档', '单元测试'],
      axisLabel: { color: ink, fontSize: 12 },
      axisLine: { lineStyle: { color: rule } }
    },
    series: [{
      type: 'bar',
      data: [
        { value: 97.2, pass: 35, total: 36, itemStyle: { color: accent2 } },
        { value: 85.7, pass: 6, total: 7, itemStyle: { color: warn } },
        { value: 87.5, pass: 7, total: 8, itemStyle: { color: warn } },
        { value: 92.9, pass: 13, total: 14, itemStyle: { color: warn } },
        { value: 94.7, pass: 18, total: 19, itemStyle: { color: accent2 } },
        { value: 87.5, pass: 7, total: 8, itemStyle: { color: warn } },
        { value: 90, pass: 9, total: 10, itemStyle: { color: warn } },
        { value: 94.7, pass: 18, total: 19, itemStyle: { color: accent2 } }
      ],
      barWidth: 18,
      label: {
        show: true, position: 'right',
        formatter: '{c}%',
        color: ink, fontSize: 11, fontWeight: 600
      },
      itemStyle: { borderRadius: [0, 3, 3, 0] }
    }]
  });
  window.addEventListener('resize', function() { chart1.resize(); });

  // Chart 2: Failure Categories (Pie)
  var chart2 = echarts.init(document.getElementById('chart-failures'), null, { renderer: 'svg' });
  chart2.setOption({
    animation: false,
    tooltip: { trigger: 'item', appendToBody: true, formatter: '{b}: {c} 项 ({d}%)' },
    legend: {
      orient: 'vertical', right: 20, top: 'center',
      textStyle: { color: ink, fontSize: 12 }
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      label: {
        show: true,
        formatter: '{b}\n{c} 项',
        fontSize: 11, color: ink
      },
      data: [
        { value: 5, name: 'CRM 受阻\n(DB未迁移)', itemStyle: { color: fail } },
        { value: 4, name: 'Alembic\nMemoryError', itemStyle: { color: warn } },
        { value: 1, name: 'FakeLLM\n断言偏差', itemStyle: { color: skip } },
        { value: 2, name: '文档版本\n号检查', itemStyle: { color: '#94a3b8' } },
        { value: 1, name: 'Workflow\n回归', itemStyle: { color: accent } }
      ]
    }]
  });
  window.addEventListener('resize', function() { chart2.resize(); });
})();