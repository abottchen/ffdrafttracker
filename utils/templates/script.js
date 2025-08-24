        // Theme toggle functionality
        const themeToggle = document.getElementById('themeToggle');
        const html = document.documentElement;

        // Check for saved theme preference or default to light
        const currentTheme = localStorage.getItem('theme') || 'light';
        html.setAttribute('data-theme', currentTheme);
        updateToggleButton(currentTheme);

        // Toggle theme on button click
        themeToggle.addEventListener('click', () => {
            const theme = html.getAttribute('data-theme');
            const newTheme = theme === 'light' ? 'dark' : 'light';

            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateToggleButton(newTheme);
        });

        function updateToggleButton(theme) {
            themeToggle.textContent = theme === 'light' ? '🌙' : '☀️';
            themeToggle.setAttribute('aria-label',
                theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode');
        }

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

        function createBarChart(containerId, data, labelKey, valueKey, title) {
            const container = document.getElementById(containerId);
            if (container.children.length > 0) return;

            const maxValue = data.length > 0 ? Math.max(...data.map(item => typeof item === 'object' ? item[valueKey] : item[1])) : 0;

            data.forEach((item, index) => {
                const label = typeof item === 'object' ? item[labelKey] : item[0];
                const value = typeof item === 'object' ? item[valueKey] : item[1];
                const percentage = maxValue > 0 ? (value / maxValue) * 100 : 0;

                const barItem = document.createElement('div');
                barItem.className = 'bar-item';

                const barHtml = '<div class="bar-label">' + label + '</div>' +
                    '<div class="bar-container">' +
                    '<div class="bar-fill" style="width: 0%"></div>' +
                    '</div>' +
                    '<div class="bar-value">' + (typeof value === 'number' && value > 100 ? '$' + value.toLocaleString() : value) + '</div>';

                barItem.innerHTML = barHtml;
                container.appendChild(barItem);

                setTimeout(() => {
                    barItem.querySelector('.bar-fill').style.width = percentage + '%';
                }, 100 + index * 50);
            });
        }

        function initializeMarketCharts() {
            createBarChart('positionBudgetChart', positionBudgetData, 0, 1, 'Position Budget');
            createBarChart('topPlayersChart', topPlayersData.map(p => [p.player_name, p.price]), 0, 1, 'Top Players');
            createBarChart('teamChart', teamData, 0, 1, 'NFL Teams');
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
                    const color = 'rgba(102, 126, 234, ' + intensity + ')';
                    rowHtml += '<div class="heatmap-cell" style="background: ' + color + '; color: ' + (intensity > 0.5 ? 'white' : 'var(--text-primary)') + '">$' + spending + '</div>';
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
                'QB': '#7b6bb5', 'RB': '#5fb572', 'WR': '#b5a55f',
                'TE': '#b5725f', 'K': '#5f82b5', 'D/ST': '#9f5f75'
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

            // Get all fantasy teams
            const fantasyTeams = new Set();
            Object.values(nflStackingData).forEach(teams => {
                Object.keys(teams).forEach(team => fantasyTeams.add(team));
            });
            const fantasyTeamsList = Array.from(fantasyTeams).sort();
            
            // Sort NFL teams by conference and division
            const nflTeamOrder = [
                // AFC East
                'BUF', 'MIA', 'NE', 'NYJ',
                // AFC North  
                'BAL', 'CIN', 'CLE', 'PIT',
                // AFC South
                'HOU', 'IND', 'JAX', 'TEN',
                // AFC West
                'DEN', 'KC', 'LV', 'LAC',
                // NFC East
                'DAL', 'NYG', 'PHI', 'WAS',
                // NFC North
                'CHI', 'DET', 'GB', 'MIN',
                // NFC South
                'ATL', 'CAR', 'NO', 'TB',
                // NFC West
                'ARI', 'LAR', 'SF', 'SEA'
            ];
            
            const nflTeamsList = Object.keys(nflStackingData).sort((a, b) => {
                const indexA = nflTeamOrder.indexOf(a);
                const indexB = nflTeamOrder.indexOf(b);
                // If team not found in order, put at end
                if (indexA === -1 && indexB === -1) return a.localeCompare(b);
                if (indexA === -1) return 1;
                if (indexB === -1) return -1;
                return indexA - indexB;
            });

            // Find the maximum count for color scaling
            let maxCount = 0;
            Object.values(nflStackingData).forEach(fantasyTeamCounts => {
                Object.values(fantasyTeamCounts).forEach(count => {
                    if (count > maxCount) maxCount = count;
                });
            });

            // Create the heatmap grid
            const heatmap = document.createElement('div');
            heatmap.className = 'nfl-stacking-heatmap';
            heatmap.style.display = 'grid';
            heatmap.style.gridTemplateColumns = `150px repeat(${fantasyTeamsList.length}, 1fr)`;
            heatmap.style.gap = '2px';
            heatmap.style.margin = '20px 0';
            heatmap.style.borderRadius = '8px';
            heatmap.style.overflow = 'hidden';

            // Create header row
            const headerRow = document.createElement('div');
            headerRow.style.display = 'contents';
            
            // Empty corner cell
            const cornerCell = document.createElement('div');
            cornerCell.className = 'heatmap-cell heatmap-header';
            cornerCell.textContent = 'NFL Team';
            headerRow.appendChild(cornerCell);

            // Fantasy team headers
            fantasyTeamsList.forEach(team => {
                const headerCell = document.createElement('div');
                headerCell.className = 'heatmap-cell heatmap-header';
                headerCell.textContent = team;
                headerCell.style.fontSize = '0.75em';
                headerRow.appendChild(headerCell);
            });
            heatmap.appendChild(headerRow);

            // Create NFL team rows with division separators
            const divisions = [
                { name: 'AFC East', teams: ['BUF', 'MIA', 'NE', 'NYJ'] },
                { name: 'AFC North', teams: ['BAL', 'CIN', 'CLE', 'PIT'] },
                { name: 'AFC South', teams: ['HOU', 'IND', 'JAX', 'TEN'] },
                { name: 'AFC West', teams: ['DEN', 'KC', 'LV', 'LAC'] },
                { name: 'NFC East', teams: ['DAL', 'NYG', 'PHI', 'WSH'] },
                { name: 'NFC North', teams: ['CHI', 'DET', 'GB', 'MIN'] },
                { name: 'NFC South', teams: ['ATL', 'CAR', 'NO', 'TB'] },
                { name: 'NFC West', teams: ['ARI', 'LAR', 'SF', 'SEA'] }
            ];

            divisions.forEach((division, divIndex) => {
                // Add division header
                const divisionHeader = document.createElement('div');
                divisionHeader.style.display = 'contents';
                
                const divHeaderCell = document.createElement('div');
                divHeaderCell.className = 'heatmap-cell';
                divHeaderCell.style.background = 'var(--alt-bg)';
                divHeaderCell.style.color = 'var(--text-secondary)';
                divHeaderCell.style.fontWeight = 'bold';
                divHeaderCell.style.fontSize = '0.8em';
                divHeaderCell.style.borderTop = divIndex > 0 ? '2px solid var(--border-color)' : 'none';
                divHeaderCell.textContent = division.name;
                divisionHeader.appendChild(divHeaderCell);
                
                // Empty cells for fantasy teams
                fantasyTeamsList.forEach(() => {
                    const emptyCell = document.createElement('div');
                    emptyCell.className = 'heatmap-cell';
                    emptyCell.style.background = 'var(--alt-bg)';
                    emptyCell.style.borderTop = divIndex > 0 ? '2px solid var(--border-color)' : 'none';
                    divisionHeader.appendChild(emptyCell);
                });
                heatmap.appendChild(divisionHeader);

                // Add team rows for this division
                division.teams.forEach(nflTeam => {
                    if (nflStackingData[nflTeam]) { // Only show teams that have data
                        const row = document.createElement('div');
                        row.style.display = 'contents';

                        // NFL team label with logo
                        const labelCell = document.createElement('div');
                        labelCell.className = 'heatmap-cell heatmap-label';
                        labelCell.style.display = 'flex';
                        labelCell.style.alignItems = 'center';
                        labelCell.style.justifyContent = 'center';
                        labelCell.style.gap = '8px';
                        
                        // Create logo image
                        const logoImg = document.createElement('img');
                        logoImg.src = '2025/assets/logos/' + nflTeam.toLowerCase() + '.png';
                        logoImg.alt = nflTeam;
                        logoImg.style.width = '24px';
                        logoImg.style.height = '24px';
                        logoImg.style.objectFit = 'contain';
                        logoImg.onerror = function() {
                            // Fallback to text if logo fails to load
                            labelCell.textContent = nflTeam;
                        };
                        
                        // Add both logo and text for better accessibility
                        const textSpan = document.createElement('span');
                        textSpan.textContent = nflTeam;
                        textSpan.style.fontSize = '0.8em';
                        
                        labelCell.appendChild(logoImg);
                        labelCell.appendChild(textSpan);
                        row.appendChild(labelCell);

                        // Fantasy team cells
                        fantasyTeamsList.forEach(fantasyTeam => {
                            const count = nflStackingData[nflTeam][fantasyTeam] || 0;
                            const intensity = maxCount > 0 ? count / maxCount : 0;
                            
                            const cell = document.createElement('div');
                            cell.className = 'heatmap-cell';
                            cell.style.background = intensity > 0 ? `rgba(102, 126, 234, ${0.2 + intensity * 0.8})` : 'transparent';
                            cell.style.color = intensity > 0.4 ? 'white' : 'var(--text-primary)';
                            cell.style.fontWeight = '600';
                            cell.textContent = count > 0 ? count : '';
                            
                            // Add tooltip
                            if (count > 0) {
                                cell.title = `${fantasyTeam} drafted ${count} ${nflTeam} player${count > 1 ? 's' : ''}`;
                            }
                            
                            row.appendChild(cell);
                        });

                        heatmap.appendChild(row);
                    }
                });
            });

            container.appendChild(heatmap);
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
                'QB': '#7b6bb5', 'RB': '#5fb572', 'WR': '#b5a55f',
                'TE': '#b5725f', 'K': '#5f82b5'
            };

            // Create tooltip element
            const tooltip = document.createElement('div');
            tooltip.style.position = 'absolute';
            tooltip.style.background = 'rgba(0, 0, 0, 0.8)';
            tooltip.style.color = 'white';
            tooltip.style.padding = '8px 12px';
            tooltip.style.borderRadius = '4px';
            tooltip.style.fontSize = '12px';
            tooltip.style.pointerEvents = 'none';
            tooltip.style.opacity = '0';
            tooltip.style.transition = 'opacity 0.2s';
            tooltip.style.zIndex = '1000';
            document.body.appendChild(tooltip);

            // Draw axes
            const axisGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            axisGroup.setAttribute('stroke', 'rgba(100, 100, 100, 0.3)');
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