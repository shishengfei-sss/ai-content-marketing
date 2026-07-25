// Charts for AI Triple Manager Unified Plan
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var bg = style.getPropertyValue('--bg').trim();

  // ============ Chart 1: Triple Manager Architecture Tree ============
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
        name: '三中枢AI系统\n',
        itemStyle: { color: ink, borderColor: ink },
        label: { fontSize: 14, fontWeight: 700, color: '#fff' },
        children: [
          {
            name: 'AI营销经理Supervisor\nP-MKT | 策略+内容+活动\n3专家Agent',
            itemStyle: { color: accent2, borderColor: accent2 },
            label: { fontSize: 12, fontWeight: 600, color: '#fff' },
            children: [
              { name: 'Strategist' },
              { name: 'Creator' },
              { name: 'Campaigner' }
            ]
          },
          {
            name: 'AI销售经理Supervisor\nP-MGR | 分析+商机+客户+教练\n4子Agent',
            itemStyle: { color: accent, borderColor: accent },
            label: { fontSize: 12, fontWeight: 600, color: '#fff' },
            children: [
              { name: '分析官 AnalystAgent' },
              { name: '商机官 OpportunityAgent' },
              { name: '客户官 CustomerAgent' },
              { name: '教练官 CoachAgent' }
            ]
          },
          {
            name: 'AI服务经理Supervisor\nP-SVC | 工单+健康+续约\n2专家Agent',
            itemStyle: { color: '#7c3aed', borderColor: '#7c3aed' },
            label: { fontSize: 12, fontWeight: 600, color: '#fff' },
            children: [
              { name: '服务官 SupportAgent' },
              { name: '客户成功官 CSMHealthAgent' }
            ]
          },
          {
            name: '共享底座',
            itemStyle: { color: '#7c3aed', borderColor: '#7c3aed' },
            label: { fontSize: 12, fontWeight: 600, color: '#fff' },
            children: [
              { name: 'Agent调度框架(C5)' },
              { name: 'Confirm闸+Workflow' },
              { name: '混合RAG(pgvector)' },
              { name: '人格库+长期记忆' },
              { name: 'CRM适配器' }
            ]
          },
          {
            name: '数据层',
            itemStyle: { color: '#0891b2', borderColor: '#0891b2' },
            label: { fontSize: 12, fontWeight: 600, color: '#fff' },
            children: [
              { name: 'CRM核心数据' },
              { name: '六大营销库' },
              { name: '销售线索/CPQ库' },
              { name: '产品价库' },
              { name: '服务六库' }
            ]
          }
        ]
      }],
      top: '6%',
      left: '12%',
      bottom: '8%',
      right: '22%',
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

  // ============ Chart 2: Responsibility Domain Radar ============
  var chartRadar = echarts.init(document.getElementById('chart-radar'), null, { renderer: 'svg' });

  var domains = [
    '战略规划', '线索/商机', '内容产出', '客户经营',
    '数据/分析', '活动/投放', '团队/协同', '品牌/公关',
    '报价/合同', '用户/增长'
  ];

  // Marketing coverage (3 expert agents, scored 0-10)
  var marketingScores = [10, 6, 10, 4, 10, 10, 7, 10, 0, 10];
  // Sales coverage (4 sub-agents, scored 0-10)
  var salesScores = [8, 10, 7, 10, 8, 2, 10, 0, 10, 3];
  // Service coverage (2 expert agents, scored 0-10)
  var serviceScores = [5, 3, 5, 10, 8, 0, 7, 3, 2, 8];

  chartRadar.setOption({
    animation: false,
    tooltip: { appendToBody: true },
    legend: {
      bottom: 0,
      textStyle: { color: ink, fontSize: 12, fontWeight: 500 },
      itemWidth: 16,
      itemHeight: 10
    },
    radar: {
      indicator: domains.map(function(d) {
        return { name: d, max: 10 };
      }),
      shape: 'polygon',
      center: ['50%', '48%'],
      radius: '65%',
      axisName: {
        color: ink,
        fontSize: 11,
        fontWeight: 500
      },
      splitArea: {
        areaStyle: { color: [bg, bg2, bg, bg2, bg] }
      },
      splitLine: {
        lineStyle: { color: rule, width: 1 }
      },
      axisLine: {
        lineStyle: { color: rule, width: 1 }
      }
    },
    series: [{
      type: 'radar',
      data: [
        {
          value: marketingScores,
          name: 'AI营销经理（3专家Agent）',
          itemStyle: { color: accent2 },
          lineStyle: { color: accent2, width: 2 },
          areaStyle: { color: accent2, opacity: 0.15 }
        },
        {
          value: salesScores,
          name: 'AI销售经理（4子Agent）',
          itemStyle: { color: accent },
          lineStyle: { color: accent, width: 2 },
          areaStyle: { color: accent, opacity: 0.15 }
        },
        {
          value: serviceScores,
          name: 'AI服务经理（2专家Agent）',
          itemStyle: { color: '#7c3aed' },
          lineStyle: { color: '#7c3aed', width: 2 },
          areaStyle: { color: '#7c3aed', opacity: 0.15 }
        }
      ]
    }]
  });
  window.addEventListener('resize', function() { chartRadar.resize(); });

  // ============ Chart 3: Unified Data Asset Hierarchy ============
  var chartData = echarts.init(document.getElementById('chart-data-layers'), null, { renderer: 'svg' });
  chartData.setOption({
    animation: false,
    tooltip: { appendToBody: true, trigger: 'item' },
    series: [{
      type: 'tree',
      data: [{
        name: '统一数据资产',
        itemStyle: { color: ink, borderColor: ink },
        label: { fontSize: 14, fontWeight: 700, color: '#fff' },
        children: [
          {
            name: 'L1: CRM核心数据\n(三中枢共用)',
            itemStyle: { color: accent, borderColor: accent },
            label: { fontSize: 12, fontWeight: 600, color: '#fff' },
            children: [
              { name: 'Lead线索' },
              { name: 'Customer客户' },
              { name: 'Deal商机' },
              { name: 'Contract合同' },
              { name: 'Payment回款' },
              { name: 'Product产品' },
              { name: 'Ticket工单' },
              { name: 'Satisfaction满意度' }
            ]
          },
          {
            name: 'L2: 营销专属数据\n(营销读写·销售/服务只读)',
            itemStyle: { color: accent2, borderColor: accent2 },
            label: { fontSize: 12, fontWeight: 600, color: '#fff' },
            children: [
              { name: '营销资料库' },
              { name: '竞品营销库' },
              { name: '活动效果库' },
              { name: '用户分层库' },
              { name: '舆情声量库' },
              { name: '行业洞察库' }
            ]
          },
          {
            name: 'L3: 销售专属数据\n(销售读写·营销/服务不访问)',
            itemStyle: { color: '#7c3aed', borderColor: '#7c3aed' },
            label: { fontSize: 12, fontWeight: 600, color: '#fff' },
            children: [
              { name: '销售线索库' },
              { name: '产品价库' },
              { name: 'CPQ引擎' }
            ]
          },
          {
            name: 'L4: 服务专属数据\n(服务读写·营销/销售只读(FAQ))',
            itemStyle: { color: '#0891b2', borderColor: '#0891b2' },
            label: { fontSize: 12, fontWeight: 600, color: '#fff' },
            children: [
              { name: '知识FAQ库' },
              { name: '工单历史库' },
              { name: '客户健康库' },
              { name: '产品使用库' },
              { name: '服务SLA库' },
              { name: '客户反馈库' }
            ]
          },
          {
            name: 'L5: 共享数据\n(三中枢只读)',
            itemStyle: { color: '#475569', borderColor: '#475569' },
            label: { fontSize: 12, fontWeight: 600, color: '#fff' },
            children: [
              { name: '营销资料库(共用)' },
              { name: '人格库' },
              { name: '长期记忆L0-L4' }
            ]
          }
        ]
      }],
      top: '6%',
      left: '12%',
      bottom: '8%',
      right: '22%',
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
  window.addEventListener('resize', function() { chartData.resize(); });

  // ============ Chart 4: Unified Gantt (Triple Manager Parallel Roadmap) ============
  var chartGantt = echarts.init(document.getElementById('chart-gantt'), null, { renderer: 'svg' });

  var phases = [
    { name: 'P0: 共享数据打通', weeks: [0, 3], color: ink },
    { name: 'P1: 三人格+骨架', weeks: [2, 5], color: accent2 },
    { name: 'P2-MKT: 营销三专家Agent', weeks: [4, 8], color: accent2 },
    { name: 'P2-SALES: 销售四子Agent', weeks: [4, 8], color: accent },
    { name: 'P2-SVC: 服务两子Agent', weeks: [4, 7], color: '#7c3aed' },
    { name: 'P3-MKT: 营销完整职能', weeks: [8, 14], color: accent2 },
    { name: 'P3-SALES: 销售完整职能', weeks: [8, 14], color: accent },
    { name: 'P3-SVC: 服务完整职能', weeks: [7, 13], color: '#7c3aed' },
    { name: 'P4: 三Manager自治闭环', weeks: [14, 18], color: '#7c3aed' },
    { name: 'P5: 三Manager自进化', weeks: [18, 26], color: muted }
  ];

  var phaseData = phases.map(function(p, i) {
    return {
      value: [i, p.weeks[0], p.weeks[1], p.weeks[1] - p.weeks[0]],
      itemStyle: { color: p.color, opacity: 0.8 }
    };
  });

  chartGantt.setOption({
    animation: false,
    tooltip: {
      appendToBody: true,
      formatter: function(params) {
        var p = phases[params.value[0]];
        return p.name + '<br/>' + (p.weeks[1] - p.weeks[0]) + ' weeks (W' + p.weeks[0] + '-W' + p.weeks[1] + ')';
      }
    },
    grid: {
      left: 200,
      right: 50,
      top: 30,
      bottom: 30
    },
    xAxis: {
      type: 'value',
      min: 0,
      max: 26,
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
        fontSize: 11,
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
        var height = api.size([0, 1])[1] * 0.55;

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
      encode: { x: [1, 2], y: 0 },
      data: phaseData,
      itemStyle: { borderRadius: 4 }
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
          return (p.weeks[1] - p.weeks[0]) + 'w';
        },
        color: muted,
        fontSize: 11,
        fontWeight: 500
      }
    }]
  });
  window.addEventListener('resize', function() { chartGantt.resize(); });

})();
