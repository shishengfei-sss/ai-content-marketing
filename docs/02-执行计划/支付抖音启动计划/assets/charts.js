(function () {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim() || '#1677ff';
  var accent2 = style.getPropertyValue('--accent2').trim() || '#0ea5e9';
  var ink = style.getPropertyValue('--ink').trim() || '#1e293b';
  var muted = style.getPropertyValue('--muted').trim() || '#64748b';
  var rule = style.getPropertyValue('--rule').trim() || '#e2e8f0';
  var warn = style.getPropertyValue('--warn').trim() || '#f59e0b';
  var danger = style.getPropertyValue('--danger').trim() || '#ef4444';
  var ok = style.getPropertyValue('--ok').trim() || '#22c55e';

  // ── Mermaid initialization ──────────────────────────────
  if (window.mermaid) {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'base',
      themeVariables: {
        primaryColor: accent,
        primaryTextColor: '#ffffff',
        primaryBorderColor: accent,
        lineColor: muted,
        secondaryColor: '#f8fafc',
        tertiaryColor: '#ffffff',
        fontFamily: 'Noto Sans SC, system-ui, sans-serif',
        fontSize: '14px',
      },
      flowchart: {
        curve: 'basis',
        padding: 16,
        nodeSpacing: 40,
        rankSpacing: 40,
      },
    });
    // Explicitly render all mermaid blocks after init
    try {
      mermaid.run({ querySelector: 'pre.mermaid' });
    } catch (e) {
      // Fallback for older Mermaid versions
      try { mermaid.init(undefined, 'pre.mermaid'); } catch (e2) {}
    }
  }

  // ── Gantt chart (parallel workstreams W1-W8) ────────────
  var ganttEl = document.getElementById('chart-gantt');
  if (ganttEl && window.echarts) {
    var chart = echarts.init(ganttEl);

    // Data: each task {name, start, end, group, milestone?}
    var categories = [
      '微信支付 · 进件',
      '微信支付 · 技术对接',
      '微信支付 · 验收',
      '抖音 · 报白',
      '抖音 · 商品上架',
      '抖音 · Mx验收',
    ];

    var weekLabels = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8'];

    var tasks = [
      // WeChat Pay
      { cat: 0, name: '服务商资质准备', start: 0, end: 1, color: accent },
      { cat: 0, name: '服务商审核+二级商户进件', start: 1, end: 3, color: accent },
      { cat: 1, name: 'JSAPI支付+回调(沙箱)', start: 2, end: 4, color: accent },
      { cat: 1, name: '退款+分账对接', start: 3, end: 5, color: accent },
      { cat: 0, name: '生产环境首批进件', start: 4, end: 5, color: accent2 },
      { cat: 2, name: 'M3-商务 私域支付', start: 5, end: 6, color: ok, milestone: true },
      { cat: 2, name: 'M5-商务 私域退款', start: 6, end: 7, color: ok, milestone: true },
      // Douyin
      { cat: 3, name: '主体资质+BD渠道', start: 0, end: 1, color: accent2 },
      { cat: 3, name: '报白资料+店铺搭建', start: 1, end: 2, color: accent2 },
      { cat: 3, name: '报白申请提交(BD通道)', start: 2, end: 4, color: accent2 },
      { cat: 4, name: '商品上架+Webhook对接', start: 4, end: 6, color: accent2 },
      { cat: 5, name: 'Mx / M7 首单', start: 6, end: 8, color: ok, milestone: true },
    ];

    var seriesData = tasks.map(function (t) {
      return {
        name: t.name,
        value: [t.cat, t.start, t.end, t.name, t.milestone ? 1 : 0, t.color],
      };
    });

    var option = {
      tooltip: {
        formatter: function (params) {
          var d = params.value;
          return d[3] + '<br/>' + weekLabels[d[1]] + ' → ' + weekLabels[Math.min(d[2] - 1, 7)];
        },
        backgroundColor: 'rgba(30,41,59,0.92)',
        borderColor: rule,
        textStyle: { color: '#fff', fontSize: 13 },
      },
      grid: {
        left: 160,
        right: 40,
        top: 40,
        bottom: 40,
      },
      xAxis: {
        type: 'value',
        min: 0,
        max: 8,
        interval: 1,
        axisLabel: {
          formatter: function (val) {
            return weekLabels[val] || '';
          },
          color: muted,
          fontSize: 12,
        },
        axisLine: { lineStyle: { color: rule } },
        splitLine: { show: true, lineStyle: { color: rule, type: 'dashed' } },
      },
      yAxis: {
        type: 'category',
        data: categories,
        inverse: true,
        axisLabel: {
          color: ink,
          fontSize: 13,
          fontWeight: 500,
        },
        axisLine: { lineStyle: { color: rule } },
        axisTick: { show: false },
      },
      series: [
        {
          type: 'custom',
          renderItem: function (params, api) {
            var catIdx = api.value(0);
            var start = api.coord([api.value(1), catIdx]);
            var end = api.coord([api.value(2), catIdx]);
            var height = api.size([0, 1])[1] * 0.5;
            var isMilestone = api.value(4) === 1;
            var color = api.value(5) || accent;

            var shape;
            if (isMilestone) {
              // Diamond shape for milestone
              var cx = (start[0] + end[0]) / 2;
              var cy = start[1];
              var s = height * 1.2;
              shape = {
                type: 'polygon',
                shape: {
                  points: [
                    [cx, cy - s],
                    [cx + s, cy],
                    [cx, cy + s],
                    [cx - s, cy],
                  ],
                },
                style: {
                  fill: color,
                  stroke: '#fff',
                  lineWidth: 2,
                },
              };
            } else {
              shape = {
                type: 'rect',
                shape: {
                  x: start[0],
                  y: start[1] - height / 2,
                  width: end[0] - start[0],
                  height: height,
                  r: 3,
                },
                style: {
                  fill: color,
                  stroke: '#fff',
                  lineWidth: 1,
                },
              };
            }

            // Label
            var labelShape = {
              type: 'text',
              style: {
                text: api.value(3),
                x: start[0] + 6,
                y: start[1] - height / 2 + 2,
                fill: '#fff',
                fontSize: 11,
                fontWeight: 600,
                overflow: 'truncate',
                width: end[0] - start[0] - 12,
              },
            };

            return isMilestone ? shape : { type: 'group', children: [shape, labelShape] };
          },
          encode: {
            x: [1, 2],
            y: 0,
          },
          data: seriesData,
        },
      ],
    };

    chart.setOption(option);
    window.addEventListener('resize', function () {
      chart.resize();
    });
  }
})();
