// assets/charts.js
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  // === Radar: Capability Overview ===
  var radar = echarts.init(document.getElementById('chart-radar'), null, { renderer: 'svg' });
  radar.setOption({
    animation: false,
    tooltip: { appendToBody: true },
    radar: {
      indicator: [
        { name: '品牌策略', max: 100 },
        { name: '市场洞察', max: 100 },
        { name: '内容策略', max: 100 },
        { name: '内容创作', max: 100 },
        { name: '活动管理', max: 100 },
        { name: '线索运营', max: 100 },
        { name: '数据分析', max: 100 },
        { name: '招标挖掘', max: 100 },
        { name: 'SEO搜索', max: 100 },
        { name: '预算管理', max: 100 }
      ],
      shape: 'circle',
      splitNumber: 4,
      axisName: { color: ink, fontSize: 12 },
      splitArea: { areaStyle: { color: ['transparent', bg2] } },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule } }
    },
    series: [{
      type: 'radar',
      data: [
        {
          value: [85, 80, 90, 95, 85, 90, 92, 88, 75, 82],
          name: 'AI营销经理',
          areaStyle: { color: accent + '33' },
          lineStyle: { color: accent, width: 2 },
          itemStyle: { color: accent }
        },
        {
          value: [40, 30, 60, 95, 20, 15, 25, 70, 70, 10],
          name: '现有小营',
          areaStyle: { color: accent2 + '22' },
          lineStyle: { color: accent2, width: 2, type: 'dashed' },
          itemStyle: { color: accent2 }
        }
      ]
    }],
    legend: {
      bottom: 0,
      textStyle: { color: muted, fontSize: 12 }
    }
  });
  window.addEventListener('resize', function() { radar.resize(); });

  // === Architecture Diagram (Tree) ===
  var arch = echarts.init(document.getElementById('chart-arch'), null, { renderer: 'svg' });
  arch.setOption({
    animation: false,
    tooltip: { appendToBody: true, trigger: 'item' },
    series: [{
      type: 'tree',
      data: [{
        name: 'MarketingBrain\n(大脑层)',
        children: [
          {
            name: 'StrategyExpert\n(市场分析)',
            children: [
              { name: 'analyze_brand_position' },
              { name: 'market_research_report' },
              { name: 'competitor_analysis' },
              { name: 'analyze_tender_opportunity' }
            ]
          },
          {
            name: 'ContentExpert\n(内容策略)',
            children: [
              { name: 'plan_content_calendar' },
              { name: 'seo_strategy' },
              { name: '调度 Creator/SEO/Compliance' }
            ]
          },
          {
            name: 'CampaignExpert\n(活动策划)',
            children: [
              { name: 'plan_campaign' },
              { name: 'budget_planning' },
              { name: 'optimize_budget' }
            ]
          },
          {
            name: 'DataExpert\n(数据分析)',
            children: [
              { name: 'analyze_funnel' },
              { name: 'marketing_dashboard_report' },
              { name: 'attribution_analysis' },
              { name: 'suggest_nurture_strategy' },
              { name: 'roi_calculator' }
            ]
          }
        ]
      }],
      left: '8%',
      right: '18%',
      top: '8%',
      bottom: '8%',
      symbol: 'roundRect',
      symbolSize: [110, 44],
      orient: 'LR',
      label: {
        position: 'inside',
        fontSize: 11,
        color: '#fff',
        fontWeight: 600
      },
      leaves: {
        label: {
          position: 'inside',
          fontSize: 10,
          color: ink,
          fontWeight: 400
        }
      },
      itemStyle: {
        color: accent,
        borderColor: accent,
        borderWidth: 1
      },
      lineStyle: {
        color: rule,
        width: 1.5,
        curveness: 0.5
      },
      emphasis: {
        focus: 'descendant',
        itemStyle: { color: accent2 }
      },
      expandAndCollapse: false,
      initialTreeDepth: -1
    }]
  });
  window.addEventListener('resize', function() { arch.resize(); });

  // === Data Flow (Sankey) ===
  var flow = echarts.init(document.getElementById('chart-dataflow'), null, { renderer: 'svg' });
  flow.setOption({
    animation: false,
    tooltip: { appendToBody: true, trigger: 'item' },
    series: [{
      type: 'sankey',
      layoutIterations: 32,
      nodeAlign: 'left',
      draggable: true,
      label: {
        color: ink,
        fontSize: 11,
        fontWeight: 600
      },
      lineStyle: {
        color: 'gradient',
        curveness: 0.5,
        opacity: 0.35
      },
      itemStyle: {
        borderWidth: 1,
        borderColor: '#fff'
      },
      data: [
        { name: 'CRM数据', itemStyle: { color: '#0f766e' } },
        { name: '营销活动', itemStyle: { color: '#0f766e' } },
        { name: '内容库', itemStyle: { color: '#0f766e' } },
        { name: '招标数据', itemStyle: { color: '#0f766e' } },
        { name: '财务数据', itemStyle: { color: '#0f766e' } },
        { name: 'MarketingBrain', itemStyle: { color: accent, borderColor: accent } },
        { name: 'StrategyExpert', itemStyle: { color: '#c2410c' } },
        { name: 'ContentExpert', itemStyle: { color: '#c2410c' } },
        { name: 'CampaignExpert', itemStyle: { color: '#c2410c' } },
        { name: 'DataExpert', itemStyle: { color: '#c2410c' } },
        { name: '执行Agent', itemStyle: { color: '#78716c' } },
        { name: '营销方案', itemStyle: { color: '#b45309' } },
        { name: '内容日历', itemStyle: { color: '#b45309' } },
        { name: '数据报告', itemStyle: { color: '#b45309' } },
        { name: '投标建议', itemStyle: { color: '#b45309' } }
      ],
      links: [
        { source: 'CRM数据', target: 'MarketingBrain', value: 10 },
        { source: '营销活动', target: 'MarketingBrain', value: 8 },
        { source: '内容库', target: 'MarketingBrain', value: 6 },
        { source: '招标数据', target: 'MarketingBrain', value: 5 },
        { source: '财务数据', target: 'MarketingBrain', value: 4 },
        { source: 'MarketingBrain', target: 'StrategyExpert', value: 8 },
        { source: 'MarketingBrain', target: 'ContentExpert', value: 7 },
        { source: 'MarketingBrain', target: 'CampaignExpert', value: 7 },
        { source: 'MarketingBrain', target: 'DataExpert', value: 9 },
        { source: 'StrategyExpert', target: '营销方案', value: 5 },
        { source: 'StrategyExpert', target: '投标建议', value: 3 },
        { source: 'ContentExpert', target: '执行Agent', value: 5 },
        { source: 'ContentExpert', target: '内容日历', value: 4 },
        { source: 'CampaignExpert', target: '营销方案', value: 4 },
        { source: 'DataExpert', target: '数据报告', value: 6 },
        { source: 'DataExpert', target: 'ContentExpert', value: 3 },
        { source: '执行Agent', target: '内容日历', value: 2 }
      ]
    }]
  });
  window.addEventListener('resize', function() { flow.resize(); });

  // === Gantt Chart ===
  var gantt = echarts.init(document.getElementById('chart-gantt'), null, { renderer: 'svg' });
  var months = ['7月', '8月', '9月', '10月', '11月', '12月', '1月', '2月', '3月', '4月', '5月', '6月'];
  var monthToIdx = {};
  months.forEach(function(m, i) { monthToIdx[m] = i; });

  function phaseData(name, startMonth, endMonth, color) {
    return {
      name: name,
      type: 'custom',
      renderItem: function(params, api) {
        var categoryIndex = api.value(0);
        var start = api.coord([api.value(1), categoryIndex]);
        var end = api.coord([api.value(2), categoryIndex]);
        var barHeight = api.size([0, 1])[1] * 0.5;
        var rectShape = echarts.graphic.clipRectByRect(
          { x: start[0], y: start[1] - barHeight / 2, width: end[0] - start[0], height: barHeight },
          { x: params.coordSys.x, y: params.coordSys.y, width: params.coordSys.width, height: params.coordSys.height }
        );
        return rectShape && {
          type: 'rect',
          transition: ['shape'],
          shape: rectShape,
          style: api.style()
        };
      },
      encode: { x: [1, 2], y: 0 },
      data: [[0, monthToIdx[startMonth], monthToIdx[endMonth] + 0.95]],
      itemStyle: { color: color }
    };
  }

  var phaseCategories = [
    '阶段一：基础整合',
    '阶段二：策略能力',
    '阶段三：自主运营',
    '阶段四：持续进化'
  ];

  gantt.setOption({
    animation: false,
    tooltip: { appendToBody: true, formatter: function(p) { return p.seriesName; } },
    dataZoom: [{ type: 'inside' }],
    grid: { left: 160, right: 30, top: 10, bottom: 30 },
    xAxis: {
      type: 'value',
      min: -0.5,
      max: 11.5,
      axisLabel: {
        formatter: function(v) { return months[v] || ''; },
        color: muted,
        fontSize: 11
      },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'category',
      data: phaseCategories,
      axisLabel: { color: ink, fontSize: 12, fontWeight: 600 },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false }
    },
    series: [
      phaseData('阶段一：基础整合（第1-3个月）', '7月', '9月', accent),
      phaseData('阶段二：策略能力（第4-6个月）', '10月', '12月', accent2),
      phaseData('阶段三：自主运营（第7-9个月）', '1月', '3月', '#a16207'),
      phaseData('阶段四：持续进化（第10-12个月）', '4月', '6月', '#166534')
    ]
  });
  window.addEventListener('resize', function() { gantt.resize(); });
})();
