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

    const balance = parseFloat(document.getElementById('account_balance').value);

    document.querySelectorAll('.total').forEach(element => {
        let value = parseFloat(element.value);
        const id = element.name.replace('-amount', '');
        if(value < 0){
            element.value = 0;
            value = 0;
        }

        totalNow += value;
        const actual = parseFloat(document.getElementById(`total-tag-before-${id}`).innerText);
        const previo = parseFloat(document.getElementById(`previous-${id}`).innerText);
        const sum =  actual - previo + value;

        document.getElementById(`total-tag-after-${id}`).innerText = isNaN(sum) ? 0 : sum.toFixed(2);
        totalAllTags += sum;
    });

    if(isNaN(totalNow))
        totalNow = 0;

    document.getElementById('total-assigned-now').innerText = totalNow.toFixed(2);
    document.getElementById('total-assigned-tags-after').innerText = totalAllTags.toFixed(2);

    let notAssigned = balance - totalNow;
    document.getElementById('not-assigned').innerText = notAssigned.toFixed(2);
}

console.log(document.querySelectorAll('.remove-btn'));


document.querySelectorAll('.remove-btn').forEach(button => {
    console.log(button);
    
    button.addEventListener('click', event => {
        console.log("PRESSED!");
        
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
