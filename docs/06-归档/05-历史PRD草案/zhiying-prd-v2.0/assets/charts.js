// assets/charts.js - Module scale visualization
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  // --- Chart: Module Scale ---
  var chartMod = echarts.init(document.getElementById('chart-module-scale'), null, { renderer: 'svg' });
  chartMod.setOption({
    animation: false,
    tooltip: { trigger: 'axis', appendToBody: true, axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '8%', bottom: '3%', top: '3%', containLabel: true },
    xAxis: { type: 'value', axisLabel: { color: muted }, axisLine: { lineStyle: { color: rule } }, splitLine: { lineStyle: { color: rule } } },
    yAxis: {
      type: 'category',
      axisLabel: { color: ink, fontSize: 12 },
      axisLine: { lineStyle: { color: rule } },
      data: ['路由模块', '服务文件', '数据迁移', 'CRM模型', '权限码', 'Web页面', 'H5页面', '测试文件']
    },
    series: [{
      type: 'bar',
      data: [
        { value: 59, itemStyle: { color: accent } },
        { value: 100, itemStyle: { color: accent2 } },
        { value: 97, itemStyle: { color: accent } },
        { value: 30, itemStyle: { color: accent2 } },
        { value: 150, itemStyle: { color: accent } },
        { value: 50, itemStyle: { color: accent2 } },
        { value: 35, itemStyle: { color: accent } },
        { value: 80, itemStyle: { color: accent2 } }
      ],
      barWidth: 22,
      label: { show: true, position: 'right', color: ink, fontSize: 12, fontWeight: 600 }
    }]
  });
  window.addEventListener('resize', function() { chartMod.resize(); });

  // --- Chart: Version Timeline ---
  var chartVer = echarts.init(document.getElementById('chart-version-timeline'), null, { renderer: 'svg' });
  chartVer.setOption({
    animation: false,
    tooltip: { trigger: 'item', appendToBody: true, formatter: function(p) { return p.name + '<br/>' + p.data.desc; } },
    grid: { left: '3%', right: '5%', bottom: '3%', top: '3%', containLabel: true },
    xAxis: { type: 'value', axisLabel: { color: muted }, axisLine: { lineStyle: { color: rule } }, splitLine: { lineStyle: { color: rule } }, name: '时间线', nameTextStyle: { color: muted } },
    yAxis: {
      type: 'category',
      inverse: true,
      axisLabel: { color: ink, fontSize: 11, fontWeight: 600 },
      axisLine: { lineStyle: { color: rule } },
      data: ['v0.3.3', 'v0.4', 'v0.5', 'v0.6', 'v0.7', 'v0.8', 'v0.9', 'v1.0', 'v1.1', 'v1.2', 'v1.3', 'v1.4', 'v1.5', 'v1.6']
    },
    series: [{
      type: 'scatter',
      symbolSize: function(val) { return val[0] * 0.6 + 12; },
      data: [
        { value: [5, 'v0.3.3'], name: '多租户+创作', desc: '账号/权限/知识库/创作/Mock发布', itemStyle: { color: accent } },
        { value: [4, 'v0.4'], name: 'Agent智能体', desc: 'ReAct/SSE/Workflow/Confirm闸', itemStyle: { color: accent } },
        { value: [6, 'v0.5'], name: 'CRM核心', desc: '线索/客户/任务/活动/自定义字段', itemStyle: { color: accent2 } },
        { value: [3, 'v0.6'], name: '统一顾问', desc: '人格库/合规自检/去掉场景UI', itemStyle: { color: accent } },
        { value: [6, 'v0.7'], name: '交易全链路', desc: '商机/产品/报价/合同/订单/回款', itemStyle: { color: accent2 } },
        { value: [5, 'v0.8'], name: '商机增强', desc: '漏斗/预测/赢输/批量/克隆', itemStyle: { color: accent } },
        { value: [7, 'v0.9'], name: '线索客户增强', desc: '评分/公海/BANT/360/培育/ROI', itemStyle: { color: accent2 } },
        { value: [7, 'v1.0'], name: '交易增强', desc: '审批/税率/合同模板/发货/发票', itemStyle: { color: accent } },
        { value: [4, 'v1.1'], name: '创作增强', desc: 'SSE/异常脱敏/活动关联/会话恢复', itemStyle: { color: accent2 } },
        { value: [4, 'v1.2'], name: '运营报表', desc: '交易报表/提醒/分配规则UI', itemStyle: { color: accent } },
        { value: [6, 'v1.3'], name: '招标+CPQ', desc: 'L1/L2/ICP/CPQ计价/毛利', itemStyle: { color: accent2 } },
        { value: [2, 'v1.4'], name: '产品主数据', desc: '规格型号字典/自定义字段/导入', itemStyle: { color: accent } },
        { value: [3, 'v1.5'], name: '价税增强', desc: '默认税率/含税语义/报价行税', itemStyle: { color: accent2 } },
        { value: [5, 'v1.6'], name: '活动增强+AI经理', desc: '活动字段/渠道字典/Supervisor三子Agent', itemStyle: { color: accent } }
      ],
      label: { show: true, position: 'right', color: ink, fontSize: 10, fontWeight: 600, formatter: '{b}' }
    }]
  });
  window.addEventListener('resize', function() { chartVer.resize(); });
})();