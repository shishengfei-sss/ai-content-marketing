/**
 * 小鹅通深度研究报告 — ECharts 图表
 * 包含：营收趋势柱状图（chart-revenue）、收入构成饼图（chart-revenue-comp）
 */

(function () {
  'use strict';

  var accentColor = '#2563eb';
  var accentColor2 = '#10b981';
  var mutedColor = '#6b7280';
  var bgColor = '#f7f8fc';

  // ============================================================
  // Chart 1: 营收与毛利率趋势（双轴柱状图 + 折线图）
  // ============================================================
  (function () {
    var dom = document.getElementById('chart-revenue');
    if (!dom) return;

    var chart = echarts.init(dom);

    var years = ['2023', '2024', '2025'];
    var revenue = [4.15, 5.21, 6.08];          // 营收（亿元）
    var grossMargin = [72.3, 74.8, 75.7];     // 毛利率（%）

    var option = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          crossStyle: { color: mutedColor }
        },
        backgroundColor: '#ffffff',
        borderColor: '#e2e5ee',
        textStyle: { color: '#1a1a2e', fontSize: 13 },
        formatter: function (params) {
          var rev = params[0];
          var gm = params[1];
          return '<strong>' + rev.axisValue + ' 年</strong><br/>' +
            rev.marker + ' 营收：<strong>' + rev.value + ' 亿元</strong><br/>' +
            gm.marker + ' 毛利率：<strong>' + gm.value + '%</strong>';
        }
      },
      legend: {
        data: ['营收（亿元）', '毛利率（%）'],
        bottom: 0,
        textStyle: { color: mutedColor, fontSize: 12 }
      },
      grid: {
        left: '8%',
        right: '8%',
        top: '12%',
        bottom: '15%'
      },
      xAxis: {
        type: 'category',
        data: years,
        axisLine: { lineStyle: { color: '#e2e5ee' } },
        axisTick: { show: false },
        axisLabel: { color: mutedColor, fontSize: 12 }
      },
      yAxis: [
        {
          type: 'value',
          name: '营收（亿元）',
          nameTextStyle: { color: mutedColor, fontSize: 11 },
          axisLine: { show: true, lineStyle: { color: '#e2e5ee' } },
          splitLine: { lineStyle: { color: '#f0f0f5', type: 'dashed' } },
          axisLabel: {
            color: mutedColor,
            fontSize: 11,
            formatter: '{value}'
          },
          min: 0,
          max: 8
        },
        {
          type: 'value',
          name: '毛利率（%）',
          nameTextStyle: { color: mutedColor, fontSize: 11 },
          axisLine: { show: false },
          splitLine: { show: false },
          axisLabel: {
            color: mutedColor,
            fontSize: 11,
            formatter: '{value}%'
          },
          min: 60,
          max: 85
        }
      ],
      series: [
        {
          name: '营收（亿元）',
          type: 'bar',
          data: revenue,
          barWidth: '40%',
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: accentColor },
              { offset: 1, color: '#3b82f6' }
            ]),
            borderRadius: [6, 6, 0, 0]
          },
          label: {
            show: true,
            position: 'top',
            color: accentColor,
            fontSize: 13,
            fontWeight: 700,
            formatter: function (p) {
              return p.value + ' 亿';
            }
          },
          emphasis: {
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#3b82f6' },
                { offset: 1, color: '#60a5fa' }
              ])
            }
          }
        },
        {
          name: '毛利率（%）',
          type: 'line',
          yAxisIndex: 1,
          data: grossMargin,
          lineStyle: {
            color: accentColor2,
            width: 2.5
          },
          itemStyle: {
            color: accentColor2
          },
          symbol: 'circle',
          symbolSize: 8,
          label: {
            show: true,
            color: accentColor2,
            fontSize: 12,
            fontWeight: 700,
            formatter: function (p) {
              return p.value + '%';
            }
          },
          smooth: true
        }
      ]
    };

    chart.setOption(option);

    // Responsive resize
    window.addEventListener('resize', function () {
      chart.resize();
    });
  })();

  // ============================================================
  // Chart 2: 2025 年收入构成（饼图）
  // ============================================================
  (function () {
    var dom = document.getElementById('chart-revenue-comp');
    if (!dom) return;

    var chart = echarts.init(dom);

    var data = [
      { value: 68.1, name: '订阅收入', itemStyle: { color: accentColor } },
      { value: 23.8, name: '云资源消耗收入', itemStyle: { color: '#3b82f6' } },
      { value: 7.5,  name: '订单处理服务收入', itemStyle: { color: accentColor2 } },
      { value: 0.6,  name: '其他', itemStyle: { color: '#94a3b8' } }
    ];

    var option = {
      tooltip: {
        trigger: 'item',
        backgroundColor: '#ffffff',
        borderColor: '#e2e5ee',
        textStyle: { color: '#1a1a2e', fontSize: 13 },
        formatter: function (p) {
          return '<strong>' + p.name + '</strong><br/>占比：<strong>' + p.value + '%</strong>';
        }
      },
      legend: {
        orient: 'vertical',
        right: '0%',
        top: 'center',
        textStyle: { color: mutedColor, fontSize: 12 },
        itemWidth: 12,
        itemHeight: 12,
        itemGap: 16
      },
      series: [
        {
          type: 'pie',
          radius: ['55%', '78%'],
          center: ['38%', '50%'],
          avoidLabelOverlap: false,
          padAngle: 2,
          itemStyle: {
            borderRadius: 6,
            borderColor: '#fff',
            borderWidth: 2
          },
          label: {
            show: true,
            position: 'inside',
            formatter: function (p) {
              return p.value + '%';
            },
            fontSize: 13,
            fontWeight: 700,
            color: '#fff'
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 16,
              fontWeight: 'bold'
            },
            scaleSize: 8
          },
          data: data
        }
      ]
    };

    chart.setOption(option);

    // Responsive resize
    window.addEventListener('resize', function () {
      chart.resize();
    });
  })();

})();