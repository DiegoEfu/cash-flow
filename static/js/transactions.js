/**
 * @file transactions.js
 * @description This file contains JavaScript functions for handling transactions-related
 * operations on the frontend. It includes functions for generating graphs using Chart.js,
 * as well as handling transaction-related events and interactions with the server.
 */

function graph() {
    /**
     * Generates a graph for the transactions of the selected account
     * using the Chart.js library.
     */
    const ctx = document.getElementById('transaction-graph').getContext('2d');
    const account = document.getElementById('account').value;   

    fetch(`/transactions/graph/${account}/`)
        .then(response => response.json())
        .then(data => {
            const chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(item => item.date), // Assuming the JSON response has a 'dates' array with the dates in each object
                    datasets: [{
                        label: 'Historic Balance of the last 30 days',
                        data: data.map(item => item.balance), // Assuming the JSON response has a 'values' array
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 2,
                        fill: false,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        x: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Date'
                            }
                        },
                        y: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Balance'
                            },
                            suggestedMin: Math.min(...data.map(item => item.balance)) - 10,
                            suggestedMax: Math.max(...data.map(item => item.balance)) + 10
                        }
                    }
                }
            });
        })
        .catch(error => console.error('Error fetching data:', error));

    const ctxTag = document.getElementById('tag-graph').getContext('2d');

    fetch(`/account/tag/graph/${account}/`)
        .then(response => response.json())
        .then(data => {
            const chartTag = new Chart(ctxTag, {
                type: 'pie',
                data: {
                    labels: data.map(item => item.tag), // Assuming the JSON response has a 'tags' array with the tag names in each object
                    datasets: [{
                        data: data.map(item => item.balance), // Assuming the JSON response has an 'amount' array with the amounts in each object
                        backgroundColor: [
                            'rgba(255, 99, 132, 0.2)',
                            'rgba(54, 162, 235, 0.2)',
                            'rgba(255, 206, 86, 0.2)',
                            'rgba(75, 192, 192, 0.2)',
                            'rgba(153, 102, 255, 0.2)',
                            'rgba(255, 159, 64, 0.2)'
                        ],
                        borderColor: [
                            'rgba(255, 99, 132, 1)',
                            'rgba(54, 162, 235, 1)',
                            'rgba(255, 206, 86, 1)',
                            'rgba(75, 192, 192, 1)',
                            'rgba(153, 102, 255, 1)',
                            'rgba(255, 159, 64, 1)'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: true,
                            text: 'Money Distribution by Tag'
                        }
                    }
                }
            });
        })
        .catch(error => console.error('Error fetching data:', error));
}

graph();