(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  // --- Chart: Priority & Effort ---
  var chartPriority = echarts.init(document.getElementById('chart-priority'), null, { renderer: 'svg' });
  chartPriority.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      appendToBody: true,
      axisPointer: { type: 'shadow' },
      formatter: function(params) {
        var p = params[0];
        return '<strong>' + p.name + '</strong><br/>预估工时: ' + p.value + ' 周';
      }
    },
    grid: {
      left: 120,
      right: 40,
      top: 40,
      bottom: 60
    },
    xAxis: {
      type: 'value',
      name: '预估工时（周）',
      nameLocation: 'middle',
      nameGap: 35,
      axisLabel: { color: muted, fontSize: 12 },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } },
      max: 7
    },
    yAxis: {
      type: 'category',
      data: [
        '管道预测仪表盘',
        'AI 销售知识问答',
        '智能跟进助手',
        'AI 客户画像',
        'AI 商机预测',
        'AI 线索评分'
      ],
      axisLabel: { color: ink, fontSize: 12 },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false }
    },
    series: [
      {
        type: 'bar',
        data: [
          { value: 5, itemStyle: { color: '#818cf8' } },
          { value: 3.5, itemStyle: { color: '#38bdf8' } },
          { value: 2.5, itemStyle: { color: '#38bdf8' } },
          { value: 2.5, itemStyle: { color: '#38bdf8' } },
          { value: 3.5, itemStyle: { color: accent } },
          { value: 2.5, itemStyle: { color: accent } }
        ],
        barWidth: 20,
        barCategoryGap: '40%',
        label: {
          show: true,
          position: 'right',
          formatter: '{c} 周',
          color: muted,
          fontSize: 11
        },
        itemStyle: {
          borderRadius: [0, 4, 4, 0]
        }
      }
    ],
    graphic: [
      {
        type: 'text',
        right: 40,
        top: 10,
        style: {
          text: '■ P0 (紧急)   ■ P1 (重要)   ■ P2 (增强)',
          fill: muted,
          fontSize: 11
        }
      }
    ]
  });
  window.addEventListener('resize', function() { chartPriority.resize(); });
})();
