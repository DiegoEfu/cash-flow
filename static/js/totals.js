document.querySelectorAll('.total').forEach(element => {
    element.addEventListener('keyup', totalKeyUp);
    element.addEventListener('change', totalChange);
});

function totalKeyUp(event) {
    calculateTotals(event);
}

function totalChange(event) {
    calculateTotals(event);
}

function calculateTotals(event) {
    let totalNow = 0;
    let totalAllTags = 0;
    let totalAllTagsMC = 0;

    const balance = parseFloat(document.getElementById('account_balance').value);
    const exchangeRate = parseFloat(document.getElementById(`exchange_rate`).value);

    document.querySelectorAll('.total').forEach(element => {
        const value = parseFloat((parseFloat(element.value)).toFixed(2));
        const valueMC = (parseFloat(element.value) * exchangeRate);
        
        const id = element.name.replace('-amount', '');
        if(value < 0){
            element.value = 0;
            value = 0;
        }
        
        totalNow += value;
        const actual = parseFloat(document.getElementById(`total-tag-before-${id}`).innerText);
        const previo = parseFloat(document.getElementById(`previous-${id}`).innerText) * exchangeRate;
        console.log(`actual: ${actual}, previo: ${previo}, value: ${value}`);
        
        const sum =  actual - previo + valueMC;

        document.getElementById(`total-tag-after-${id}`).innerText = isNaN(sum) ? 0 : sum.toFixed(2);
        totalAllTagsMC += sum;
    });

    if(isNaN(totalNow))
        totalNow = 0;

    document.getElementById('total-assigned-now').innerText = (totalNow).toFixed(2);
    document.getElementById('total-assigned-tags-after').innerText = totalAllTagsMC.toFixed(2);

    const notAssignedMC = balance * exchangeRate - totalNow * exchangeRate;
    const notAssigned = balance - totalNow;
    document.getElementById('not-assigned').innerText = `${document.getElementById('account_currency').value} ${notAssigned.toFixed(2)} / ${document.getElementById('main_currency').value} ${notAssignedMC.toFixed(2)}`; ;
}

document.querySelectorAll('.remove-btn').forEach(button => {
    console.log(button);
    
    button.addEventListener('click', event => {       
        const row = event.target.closest('tr');
        const table = event.target.closest('table');
        const rows = table.rows;
        
        row.remove();
        calculateTotals(event);

        for(let i = 1; i < rows.length - 2; i++){
            const row = rows[i];
            row.cells[0].textContent = i;
        }
    });
});
