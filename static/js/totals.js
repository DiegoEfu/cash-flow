document.querySelectorAll('.total').forEach(element => {
    element.addEventListener('keyup', totalKeyUp);
    element.addEventListener('change', totalChange);
    element.addEventListener('focus', function() {
        this.dataset.previousValue = this.value;
    });
});

function totalKeyUp(event) {
    calculateTotals(event);
}

function totalChange(event) {
    calculateTotals(event);
}

function calculateTotals(event) {
    let totalNow = 0;
    let totalTags = 0;
    let totalAllTags = 0;

    const balance = parseFloat(document.getElementById('account_balance').value);

    document.querySelectorAll('.total').forEach(element => {
        let value = parseFloat(element.value);
        if(value < 0){
            element.value = 0;
            value = 0;
        }

        totalNow += value;
    });

    if(isNaN(totalNow))
        totalNow = 0;

    document.getElementById('total-assigned-now').innerText = totalNow.toFixed(2);

    let notAssigned = balance - totalNow;
    document.getElementById('not-assigned').innerText = notAssigned.toFixed(2);

    document.querySelectorAll('.total-tag').forEach(element => {
        let value = parseFloat(element.innerText);
        if(value < 0){
            element.value = 0;
            value = 0;
        }

        totalTags += value;
    });
    document.getElementById('total-assigned-tags').innerText = totalTags.toFixed(2);

    document.querySelectorAll('.total-tag').forEach(element => {
        if(element.previousElementSibling === event.target) {
            element.innerText = totalTags.toFixed(2);
        }
    });

    document.querySelectorAll('.total-tag').forEach(element => {
        let value = parseFloat(element.innerText);
        if(value < 0){
            element.value = 0;
            value = 0;
        }

        totalAllTags += value;
        if(element === event.target) {
            totalAllTags -= parseFloat(element.dataset.previousValue);
        }
    });

    document.getElementById('total-assigned-tags').innerText = totalAllTags.toFixed(2);
    event.target.dataset.previousValue = event.target.value;
}

