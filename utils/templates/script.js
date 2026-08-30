        // Draft crawl: auto-rolls, and can be grabbed and dragged to seek
        (function () {
            const viewport = document.querySelector('.tape-viewport');
            const track = document.querySelector('.tape-track');
            const reel = document.querySelector('.tape-reel');
            if (!viewport || !track || !reel) return;
            if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

            const canHover = window.matchMedia('(hover: hover)').matches;
            let offset = 0;
            let hovering = false;
            let dragging = false;
            let lastX = 0;
            let lastTime = null;

            function frame(now) {
                if (lastTime === null) lastTime = now;
                const dt = (now - lastTime) / 1000;
                lastTime = now;

                const reelWidth = reel.offsetWidth;
                if (reelWidth > 0) {
                    // one full loop every ~300s, matching a broadcast crawl pace
                    const speed = Math.max(60, reelWidth / 300);
                    if (!hovering && !dragging) offset += speed * dt;
                    offset = ((offset % reelWidth) + reelWidth) % reelWidth;
                    track.style.transform = 'translateX(' + (-offset) + 'px)';
                }
                requestAnimationFrame(frame);
            }
            requestAnimationFrame(frame);

            viewport.addEventListener('pointerdown', (e) => {
                dragging = true;
                lastX = e.clientX;
                viewport.setPointerCapture(e.pointerId);
                viewport.classList.add('dragging');
            });
            viewport.addEventListener('pointermove', (e) => {
                if (!dragging) return;
                offset -= e.clientX - lastX;
                lastX = e.clientX;
            });
            function endDrag() {
                dragging = false;
                viewport.classList.remove('dragging');
            }
            viewport.addEventListener('pointerup', endDrag);
            viewport.addEventListener('pointercancel', endDrag);

            // pause to read under a mouse; touch has drag instead
            if (canHover) {
                viewport.addEventListener('mouseenter', () => { hovering = true; });
                viewport.addEventListener('mouseleave', () => { hovering = false; });
            }
        })();

        // Layout toggle functionality
        const layoutToggle = document.getElementById('layoutToggle');
        const teamsGrid = document.getElementById('teamsGrid');

        // Check for saved layout preference or default to grid
        const currentLayout = localStorage.getItem('layout') || 'grid';
        if (currentLayout === 'list') {
            teamsGrid.classList.add('list-layout');
            updateLayoutButton('list');
        }

        // Toggle layout on button click
        layoutToggle.addEventListener('click', () => {
            const isListLayout = teamsGrid.classList.contains('list-layout');
            const newLayout = isListLayout ? 'grid' : 'list';

            if (newLayout === 'list') {
                teamsGrid.classList.add('list-layout');
            } else {
                teamsGrid.classList.remove('list-layout');
            }

            localStorage.setItem('layout', newLayout);
            updateLayoutButton(newLayout);
        });

        function updateLayoutButton(layout) {
            const icon = layoutToggle.querySelector('.layout-icon');
            const text = layoutToggle.querySelector('.layout-text');

            if (layout === 'grid') {
                icon.textContent = '⊞';
                text.textContent = 'Grid View';
                layoutToggle.setAttribute('aria-label', 'Switch to list view');
            } else {
                icon.textContent = '☰';
                text.textContent = 'List View';
                layoutToggle.setAttribute('aria-label', 'Switch to grid view');
            }
        }

        // Tab functionality for draft summary
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                // Remove active class from all tabs and content
                document.querySelectorAll('.tab-btn, .tab-content').forEach(el =>
                    el.classList.remove('active'));

                // Add active class to clicked tab and corresponding content
                btn.classList.add('active');
                document.getElementById(btn.dataset.tab).classList.add('active');

                // Initialize charts when tabs are opened
                if (btn.dataset.tab === 'market') {
                    initializeMarketCharts();
                } else if (btn.dataset.tab === 'teams') {
                    initializeTeamCharts();
                } else if (btn.dataset.tab === 'value') {
                    initializeValueCharts();
                }
            });
        });

        // Chart data
        const teamData = {TEAM_DATA};
        const positionBudgetData = {POSITION_BUDGET_DATA};
        const positionRangeData = {POSITION_RANGE_DATA};
        const topPlayersData = {TOP_PLAYERS_DATA};
        const teamBudgetData = {TEAM_BUDGET_DATA};
        const rosterMatrixData = {ROSTER_MATRIX_DATA};
        const nflStackingData = {NFL_STACKING_DATA};
        const valueScatterData = {VALUE_SCATTER_DATA};

        function createBarChart(containerId, data, labelKey, valueKey, money) {
            const container = document.getElementById(containerId);
            if (container.children.length > 0) return;

            const maxValue = data.length > 0 ? Math.max(...data.map(item => typeof item === 'object' ? item[valueKey] : item[1])) : 0;

            data.forEach((item, index) => {
                const label = typeof item === 'object' ? item[labelKey] : item[0];
                const value = typeof item === 'object' ? item[valueKey] : item[1];
                const percentage = maxValue > 0 ? (value / maxValue) * 100 : 0;

                const barItem = document.createElement('div');
                barItem.className = 'bar-item';

                const display = money ? '$' + value.toLocaleString() : value;
                const barHtml = '<div class="bar-label">' + label + '</div>' +
                    '<div class="bar-container">' +
                    '<div class="bar-fill' + (money ? '' : ' count') + '" style="width: 0%"></div>' +
                    '</div>' +
                    '<div class="bar-value' + (money ? '' : ' count') + '">' + display + '</div>';

                barItem.innerHTML = barHtml;
                container.appendChild(barItem);

                setTimeout(() => {
                    barItem.querySelector('.bar-fill').style.width = percentage + '%';
                }, 100 + index * 50);
            });
        }

        function initializeMarketCharts() {
            createBarChart('positionBudgetChart', positionBudgetData, 0, 1, true);
            createBarChart('topPlayersChart', topPlayersData.map(p => [p.player_name, p.price]), 0, 1, true);
            createBarChart('teamChart', teamData, 0, 1, false);
            initializePositionRangeChart();
        }

        function initializeTeamCharts() {
            initializeRosterHeatmap();
            initializeRosterStackedChart();
            initializeNFLStackingChart();
        }

        function initializeValueCharts() {
            initializeScatterPlot();
        }

        function initializePositionRangeChart() {
            const container = document.getElementById('positionAvgChart');
            if (container.children.length > 0) return;

            const maxValue = Math.max(...positionRangeData.map(p => p.max));

            positionRangeData.forEach((item, index) => {
                const percentage = maxValue > 0 ? (item.avg / maxValue) * 100 : 0;

                const barItem = document.createElement('div');
                barItem.className = 'bar-item';

                const barHtml = '<div class="bar-label">' + item.position + '</div>' +
                    '<div class="bar-container">' +
                    '<div class="bar-fill" style="width: 0%; background: ' + item.color + '"></div>' +
                    '</div>' +
                    '<div class="bar-value">$' + Math.round(item.avg) + '</div>';

                barItem.innerHTML = barHtml;
                container.appendChild(barItem);

                setTimeout(() => {
                    barItem.querySelector('.bar-fill').style.width = percentage + '%';
                }, 100 + index * 50);
            });
        }

        function initializeRosterHeatmap() {
            const container = document.getElementById('rosterHeatmap');
            if (container.children.length > 0) return;

            const positions = ['QB', 'RB', 'WR', 'TE', 'K', 'D/ST'];
            const teams = Object.keys(rosterMatrixData);
            const maxSpending = Math.max(...teams.flatMap(team => positions.map(pos => rosterMatrixData[team][pos] || 0)));

            // Create header row
            const headerRow = document.createElement('div');
            headerRow.className = 'heatmap-row';
            headerRow.style.gridTemplateColumns = '150px repeat(' + positions.length + ', 1fr)';

            headerRow.innerHTML = '<div class="heatmap-cell heatmap-header">Team</div>' +
                positions.map(pos => '<div class="heatmap-cell heatmap-header">' + pos + '</div>').join('');
            container.appendChild(headerRow);

            // Create team rows
            teams.forEach(team => {
                const row = document.createElement('div');
                row.className = 'heatmap-row';
                row.style.gridTemplateColumns = '150px repeat(' + positions.length + ', 1fr)';

                let rowHtml = '<div class="heatmap-cell heatmap-label">' + team + '</div>';
                positions.forEach(pos => {
                    const spending = rosterMatrixData[team][pos] || 0;
                    const intensity = maxSpending > 0 ? spending / maxSpending : 0;
                    const color = 'rgba(226, 184, 76, ' + (intensity * 0.9) + ')';
                    rowHtml += '<div class="heatmap-cell" style="background: ' + color + '; color: ' + (intensity > 0.35 ? 'var(--ink-on-bright)' : 'var(--text-primary)') + '">$' + spending + '</div>';
                });

                row.innerHTML = rowHtml;
                container.appendChild(row);
            });
        }

        function initializeRosterStackedChart() {
            const container = document.getElementById('rosterStackedChart');
            if (container.children.length > 0) return;

            const positions = ['QB', 'RB', 'WR', 'TE', 'K', 'D/ST'];
            const positionColors = {
                'QB': '#A995E8', 'RB': '#6FD08C', 'WR': '#E8CE6B',
                'TE': '#E8926F', 'K': '#7FA8E8', 'D/ST': '#D07A96'
            };

            // Create legend
            const legend = document.createElement('div');
            legend.className = 'stacked-legend';
            positions.forEach(pos => {
                const legendItem = document.createElement('div');
                legendItem.className = 'legend-item';
                legendItem.innerHTML = `
                    <div class="legend-color" style="background: ${positionColors[pos]}"></div>
                    <span>${pos}</span>
                `;
                legend.appendChild(legendItem);
            });
            container.appendChild(legend);

            const teams = Object.keys(rosterMatrixData);
            teams.forEach(teamName => {
                const teamData = rosterMatrixData[teamName];
                const totalSpending = positions.reduce((sum, pos) => sum + (teamData[pos] || 0), 0);

                if (totalSpending === 0) return;

                const barItem = document.createElement('div');
                barItem.className = 'stacked-bar-item';

                const label = document.createElement('div');
                label.className = 'stacked-bar-label';
                label.textContent = teamName;

                const barContainer = document.createElement('div');
                barContainer.className = 'stacked-bar-container';

                const total = document.createElement('div');
                total.className = 'stacked-bar-total';
                total.textContent = '$' + totalSpending;

                positions.forEach(pos => {
                    const spending = teamData[pos] || 0;
                    if (spending > 0) {
                        const percentage = (spending / totalSpending) * 100;
                        const segment = document.createElement('div');
                        segment.className = 'stacked-bar-segment';
                        segment.style.width = percentage + '%';
                        segment.style.background = positionColors[pos];

                        // Only show text if segment is wide enough
                        if (percentage > 8) {
                            segment.textContent = '$' + spending;
                        }

                        // Add tooltip
                        segment.title = `${pos}: $${spending} (${percentage.toFixed(1)}%)`;

                        barContainer.appendChild(segment);
                    }
                });

                barItem.appendChild(label);
                barItem.appendChild(barContainer);
                barItem.appendChild(total);
                container.appendChild(barItem);
            });
        }

        function initializeNFLStackingChart() {
            const container = document.getElementById('nflStackingChart');
            if (container.children.length > 0) return;

            // Fantasy team columns (alphabetical)
            const fantasyTeams = new Set();
            Object.values(nflStackingData).forEach(teams => {
                Object.keys(teams).forEach(team => fantasyTeams.add(team));
            });
            const fantasyTeamsList = Array.from(fantasyTeams).sort();

            let maxCount = 0;
            Object.values(nflStackingData).forEach(counts => {
                Object.values(counts).forEach(c => { if (c > maxCount) maxCount = c; });
            });

            const conferences = [
                { name: 'AFC', divisions: [
                    { name: 'East', teams: ['BUF', 'MIA', 'NE', 'NYJ'] },
                    { name: 'North', teams: ['BAL', 'CIN', 'CLE', 'PIT'] },
                    { name: 'South', teams: ['HOU', 'IND', 'JAX', 'TEN'] },
                    { name: 'West', teams: ['DEN', 'KC', 'LV', 'LAC'] }
                ] },
                { name: 'NFC', divisions: [
                    { name: 'East', teams: ['DAL', 'NYG', 'PHI', 'WAS'] },
                    { name: 'North', teams: ['CHI', 'DET', 'GB', 'MIN'] },
                    { name: 'South', teams: ['ATL', 'CAR', 'NO', 'TB'] },
                    { name: 'West', teams: ['ARI', 'LAR', 'SF', 'SEA'] }
                ] }
            ];

            const wrap = document.createElement('div');
            wrap.className = 'stacking-wrap';

            conferences.forEach(conference => {
                const conf = document.createElement('div');
                conf.className = 'stacking-conf';

                const title = document.createElement('div');
                title.className = 'stacking-conf-title';
                title.textContent = conference.name;
                conf.appendChild(title);

                const grid = document.createElement('div');
                grid.className = 'stacking-grid';
                grid.style.gridTemplateColumns =
                    '86px repeat(' + fantasyTeamsList.length + ', 1fr)';

                // Header: rotated fantasy team names
                const corner = document.createElement('div');
                grid.appendChild(corner);
                fantasyTeamsList.forEach(team => {
                    const head = document.createElement('div');
                    head.className = 'stacking-colhead';
                    head.textContent = team;
                    head.title = team;
                    grid.appendChild(head);
                });

                conference.divisions.forEach(division => {
                    const withData = division.teams.filter(t => nflStackingData[t]);
                    if (withData.length === 0) return;

                    // Slim division separator
                    const divLabel = document.createElement('div');
                    divLabel.className = 'stacking-div';
                    divLabel.textContent = division.name;
                    grid.appendChild(divLabel);
                    fantasyTeamsList.forEach(() => {
                        const spacer = document.createElement('div');
                        spacer.className = 'stacking-div';
                        grid.appendChild(spacer);
                    });

                    withData.forEach(nflTeam => {
                        const label = document.createElement('div');
                        label.className = 'stacking-teamlabel';

                        const logo = document.createElement('img');
                        logo.src = '{YEAR}/assets/logos/' + nflTeam.toLowerCase() + '.png';
                        logo.alt = '';
                        logo.onerror = function () { this.remove(); };
                        label.appendChild(logo);
                        label.appendChild(document.createTextNode(nflTeam));
                        grid.appendChild(label);

                        fantasyTeamsList.forEach(fantasyTeam => {
                            const count = nflStackingData[nflTeam][fantasyTeam] || 0;
                            const intensity = maxCount > 0 ? count / maxCount : 0;
                            const cell = document.createElement('div');
                            cell.className = 'stacking-cell';
                            if (count > 0) {
                                cell.style.background =
                                    'rgba(226, 184, 76, ' + (0.15 + intensity * 0.75) + ')';
                                cell.style.color = intensity > 0.35
                                    ? 'var(--ink-on-bright)' : 'var(--text-primary)';
                                cell.textContent = count;
                                cell.title = fantasyTeam + ' drafted ' + count + ' ' +
                                    nflTeam + ' player' + (count > 1 ? 's' : '');
                            }
                            grid.appendChild(cell);
                        });
                    });
                });

                conf.appendChild(grid);
                wrap.appendChild(conf);
            });

            container.appendChild(wrap);
        }

        function initializeScatterPlot() {
            const container = document.getElementById('valueScatter');
            if (container.children.length > 0) return;

            // Create SVG instead of canvas for better interactivity
            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('width', '100%');
            svg.setAttribute('height', '500');
            svg.style.border = '1px solid var(--border-color)';
            svg.style.borderRadius = '8px';
            svg.style.background = 'var(--card-bg)';

            const width = 1200;
            const height = 500;
            const padding = 60;
            const plotWidth = width - 2 * padding;
            const plotHeight = height - 2 * padding;

            svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
            container.appendChild(svg);

            const maxPrice = Math.max(...valueScatterData.map(d => d.price));
            const maxPoints = Math.max(...valueScatterData.map(d => d.points));

            // Position colors
            const positionColors = {
                'QB': '#A995E8', 'RB': '#6FD08C', 'WR': '#E8CE6B',
                'TE': '#E8926F', 'K': '#7FA8E8', 'D/ST': '#D07A96'
            };

            // Create tooltip element
            const tooltip = document.createElement('div');
            tooltip.style.position = 'absolute';
            tooltip.style.background = 'rgba(10, 13, 20, 0.94)';
            tooltip.style.color = 'white';
            tooltip.style.padding = '8px 12px';
            tooltip.style.borderRadius = '3px';
            tooltip.style.border = '1px solid rgba(240, 242, 245, 0.2)';
            tooltip.style.fontSize = '12px';
            tooltip.style.pointerEvents = 'none';
            tooltip.style.opacity = '0';
            tooltip.style.transition = 'opacity 0.2s';
            tooltip.style.zIndex = '1000';
            document.body.appendChild(tooltip);

            // Draw axes
            const axisGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            axisGroup.setAttribute('stroke', 'rgba(240, 242, 245, 0.18)');
            axisGroup.setAttribute('stroke-width', '2');

            // Y axis
            const yAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            yAxis.setAttribute('x1', padding);
            yAxis.setAttribute('y1', padding);
            yAxis.setAttribute('x2', padding);
            yAxis.setAttribute('y2', height - padding);
            axisGroup.appendChild(yAxis);

            // X axis
            const xAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            xAxis.setAttribute('x1', padding);
            xAxis.setAttribute('y1', height - padding);
            xAxis.setAttribute('x2', width - padding);
            xAxis.setAttribute('y2', height - padding);
            axisGroup.appendChild(xAxis);

            svg.appendChild(axisGroup);

            // Add axis labels
            const xLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            xLabel.setAttribute('x', width / 2);
            xLabel.setAttribute('y', height - 10);
            xLabel.setAttribute('text-anchor', 'middle');
            xLabel.setAttribute('font-size', '14');
            xLabel.setAttribute('fill', 'var(--text-primary)');
            xLabel.textContent = 'Auction Price ($)';
            svg.appendChild(xLabel);

            const yLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            yLabel.setAttribute('x', 20);
            yLabel.setAttribute('y', height / 2);
            yLabel.setAttribute('text-anchor', 'middle');
            yLabel.setAttribute('font-size', '14');
            yLabel.setAttribute('fill', 'var(--text-primary)');
            yLabel.setAttribute('transform', `rotate(-90, 20, ${height / 2})`);
            yLabel.textContent = 'Fantasy Points';
            svg.appendChild(yLabel);

            // Draw points
            valueScatterData.forEach(point => {
                const x = padding + (point.price / maxPrice) * plotWidth;
                const y = height - padding - (point.points / maxPoints) * plotHeight;

                const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('cx', x);
                circle.setAttribute('cy', y);
                circle.setAttribute('r', 6);
                circle.setAttribute('fill', positionColors[point.position] || '#666');
                circle.style.cursor = 'pointer';
                circle.style.transition = 'r 0.2s';

                // Add hover effects and tooltip
                circle.addEventListener('mouseenter', (e) => {
                    circle.setAttribute('r', 8);
                    tooltip.innerHTML = `
                        <strong>${point.name}</strong><br>
                        Position: ${point.position}<br>
                        Price: $${point.price}<br>
                        Fantasy Points: ${point.points.toFixed(1)}<br>
                        Team: ${point.team}
                    `;
                    tooltip.style.opacity = '1';
                });

                circle.addEventListener('mousemove', (e) => {
                    tooltip.style.left = (e.pageX + 10) + 'px';
                    tooltip.style.top = (e.pageY - 10) + 'px';
                });

                circle.addEventListener('mouseleave', () => {
                    circle.setAttribute('r', 6);
                    tooltip.style.opacity = '0';
                });

                svg.appendChild(circle);
            });

            // Add position legend
            const legend = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            legend.setAttribute('transform', `translate(${width - 120}, 30)`);

            const positions = Object.keys(positionColors);
            positions.forEach((pos, i) => {
                const legendItem = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                legendItem.setAttribute('transform', `translate(0, ${i * 20})`);

                const legendCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                legendCircle.setAttribute('cx', 6);
                legendCircle.setAttribute('cy', 6);
                legendCircle.setAttribute('r', 4);
                legendCircle.setAttribute('fill', positionColors[pos]);
                legendItem.appendChild(legendCircle);

                const legendText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                legendText.setAttribute('x', 16);
                legendText.setAttribute('y', 10);
                legendText.setAttribute('font-size', '12');
                legendText.setAttribute('fill', 'var(--text-primary)');
                legendText.textContent = pos;
                legendItem.appendChild(legendText);

                legend.appendChild(legendItem);
            });

            svg.appendChild(legend);
        }