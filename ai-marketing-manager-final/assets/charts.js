// Charts for AI Marketing Manager Final Plan
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var bg = style.getPropertyValue('--bg').trim();

  // ============ Chart 1: Architecture Tree (3 Expert Agents) ============
  var chartArch = echarts.init(document.getElementById('chart-arch'), null, { renderer: 'svg' });
  chartArch.setOption({
    animation: false,
    tooltip: {
      appendToBody: true,
      trigger: 'item',
      triggerOn: 'mousemove'
    },
    series: [{
      type: 'tree',
      data: [{
        name: 'AI营销经理Supervisor\n(大脑层)\n意图路由·任务拆分·结果汇总·Confirm闸·周报月报',
        itemStyle: { color: accent, borderColor: accent },
        label: {
          fontSize: 13,
          fontWeight: 700,
          color: ink
        },
        children: [
          {
            name: '策略洞察官\nStrategist\n"想清楚打什么仗"',
            itemStyle: { color: accent2, borderColor: accent2 },
            label: { fontSize: 12, fontWeight: 600, color: ink },
            children: [
              { name: '品牌定位分析' },
              { name: '市场研究报告' },
              { name: '竞品打法拆解' },
              { name: '行业趋势研究' },
              { name: 'ROI/归因分析' },
              { name: '招标机会分析' }
            ]
          },
          {
            name: '内容品牌官\nCreator\n"说什么、怎么说"',
            itemStyle: { color: '#7c3aed', borderColor: '#7c3aed' },
            label: { fontSize: 12, fontWeight: 600, color: ink },
            children: [
              { name: '内容日历规划' },
              { name: '多形态文案创作' },
              { name: 'SEO策略' },
              { name: '品牌TONE校验' },
              { name: '公关稿/危机口径' }
            ]
          },
          {
            name: '活动增长官\nCampaigner\n"在哪打、怎么打"',
            itemStyle: { color: '#0891b2', borderColor: '#0891b2' },
            label: { fontSize: 12, fontWeight: 600, color: ink },
            children: [
              { name: '活动策划与SOP' },
              { name: '预算规划与优化' },
              { name: '投放优化' },
              { name: '线索培育MQL→SQL' },
              { name: '活动复盘' },
              { name: '漏斗分析' }
            ]
          }
        ]
      }],
      top: '8%',
      left: '5%',
      bottom: '5%',
      right: '25%',
      symbolSize: 14,
      symbol: 'circle',
      orient: 'LR',
      expandAndCollapse: false,
      initialTreeDepth: 2,
      label: {
        position: 'left',
        verticalAlign: 'middle',
        align: 'right',
        fontSize: 11,
        color: ink,
        fontWeight: 500,
        lineHeight: 14
      },
      leaves: {
        label: {
          position: 'right',
          verticalAlign: 'middle',
          align: 'left',
          fontSize: 10,
          fontWeight: 400,
          color: muted
        }
      },
      emphasis: {
        focus: 'descendant'
      },
      lineStyle: {
        color: rule,
        width: 1.5,
        curveness: 0.5
      }
    }]
  });
  window.addEventListener('resize', function() { chartArch.resize(); });

  // ============ Chart 2: Gantt / Phase Timeline ============
  var chartGantt = echarts.init(document.getElementById('chart-gantt'), null, { renderer: 'svg' });

  var phases = [
    { name: 'Phase 0: 数据地基', weeks: [0, 3], color: accent },
    { name: 'Phase 1: 人格+骨架', weeks: [2, 4], color: accent2 },
    { name: 'Phase 2: 三大子Agent', weeks: [4, 8], color: '#7c3aed' },
    { name: 'Phase 3: 完整职能', weeks: [8, 14], color: '#0891b2' },
    { name: 'Phase 4: 自治闭环', weeks: [14, 18], color: '#16a34a' },
    { name: 'Phase 5: 自进化', weeks: [18, 24], color: muted }
  ];

  var phaseData = phases.map(function(p, i) {
    return {
      value: [i, p.weeks[0], p.weeks[1], p.weeks[1] - p.weeks[0]],
      itemStyle: { color: p.color }
    };
  });

  var weekLabels = [];
  for (var w = 0; w <= 24; w += 2) {
    weekLabels.push('W' + w);
  }

  chartGantt.setOption({
    animation: false,
    tooltip: {
      appendToBody: true,
      formatter: function(params) {
        var p = phases[params.value[0]];
        return p.name + '<br/>周期：' + (p.weeks[1] - p.weeks[0]) + '周 (W' + p.weeks[0] + '-W' + p.weeks[1] + ')';
      }
    },
    grid: {
      left: 180,
      right: 40,
      top: 30,
      bottom: 30
    },
    xAxis: {
      type: 'value',
      min: 0,
      max: 24,
      axisLabel: {
        formatter: function(v) { return 'W' + v; },
        color: muted,
        fontSize: 11
      },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    yAxis: {
      type: 'category',
      data: phases.map(function(p) { return p.name; }),
      axisLabel: {
        color: ink,
        fontSize: 12,
        fontWeight: 500
      },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    series: [{
      type: 'custom',
      renderItem: function(params, api) {
        var categoryIndex = api.value(0);
        var start = api.coord([api.value(1), categoryIndex]);
        var end = api.coord([api.value(2), categoryIndex]);
        var height = api.size([0, 1])[1] * 0.6;

        var rectShape = echarts.graphic.clipRectByRect({
          x: start[0],
          y: start[1] - height / 2,
          width: end[0] - start[0],
          height: height
        }, {
          x: params.coordSys.x,
          y: params.coordSys.y,
          width: params.coordSys.width,
          height: params.coordSys.height
        });

        return rectShape && {
          type: 'rect',
          transition: ['shape'],
          shape: rectShape,
          style: api.style()
        };
      },
      encode: {
        x: [1, 2],
        y: 0
      },
      data: phaseData,
      itemStyle: {
        borderRadius: 4,
        opacity: 0.85
      }
    }, {
      type: 'scatter',
      data: phases.map(function(p, i) {
        return [p.weeks[1], i];
      }),
      symbol: 'none',
      label: {
        show: true,
        position: 'right',
        formatter: function(params) {
          var p = phases[params.value[1]];
          return (p.weeks[1] - p.weeks[0]) + '周';
        },
        color: muted,
        fontSize: 11,
        fontWeight: 500
      }
    }]
  });
  window.addEventListener('resize', function() { chartGantt.resize(); });

  // ============ Chart 3: Agent Structure (4 Elements) ============
  var chartAgentStruct = echarts.init(document.getElementById('chart-agent-struct'), null, { renderer: 'svg' });
  chartAgentStruct.setOption({
    animation: false,
    tooltip: { appendToBody: true, trigger: 'item' },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: false,
      draggable: false,
      force: {
        repulsion: 400,
        edgeLength: [100, 140],
        gravity: 0.12
      },
      label: {
        show: true,
        position: 'inside',
        fontSize: 12,
        fontWeight: 600,
        color: '#fff',
        formatter: function(p) { return p.data.label; }
      },
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [0, 8],
      lineStyle: {
        color: rule,
        width: 2,
        curveness: 0.1
      },
      emphasis: {
        lineStyle: { width: 3, color: accent }
      },
      data: [
        { name: 'core', label: 'Agent\n核心', x: 0, y: 0, symbolSize: 90, itemStyle: { color: accent }, fixed: true },
        { name: 'data', label: '资料库\n读什么数据', symbolSize: 65, itemStyle: { color: accent2 } },
        { name: 'skill', label: 'Skill\n能调什么工具', symbolSize: 65, itemStyle: { color: '#7c3aed' } },
        { name: 'workflow', label: '工作流\n怎么编排', symbolSize: 65, itemStyle: { color: '#0891b2' } },
        { name: 'prompt', label: '提示词\n怎么思考', symbolSize: 65, itemStyle: { color: '#16a34a' } },
        { name: 'd1', label: '竞品库', symbolSize: 35, itemStyle: { color: accent2, opacity: 0.6 }, label: { fontSize: 9 } },
        { name: 'd2', label: '活动效果库', symbolSize: 35, itemStyle: { color: accent2, opacity: 0.6 }, label: { fontSize: 9 } },
        { name: 'd3', label: '行业洞察库', symbolSize: 35, itemStyle: { color: accent2, opacity: 0.6 }, label: { fontSize: 9 } },
        { name: 'd4', label: '用户分层库', symbolSize: 35, itemStyle: { color: accent2, opacity: 0.6 }, label: { fontSize: 9 } }
      ],
      links: [
        { source: 'core', target: 'data' },
        { source: 'core', target: 'skill' },
        { source: 'core', target: 'workflow' },
        { source: 'core', target: 'prompt' },
        { source: 'data', target: 'd1' },
        { source: 'data', target: 'd2' },
        { source: 'data', target: 'd3' },
        { source: 'data', target: 'd4' }
      ]
    }]
  });
  window.addEventListener('resize', function() { chartAgentStruct.resize(); });

})();
