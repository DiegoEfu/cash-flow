/**
 * @file form.js
 * @description This file contains the JavaScript code for the totals input fields. It
 * listens for keyup and change events on the .total class and then
 * recalculates the total values.
 *
 * The total values are the sum of all the values in all the .total fields.
 *
 * The total values are displayed in the elements with the class .totals.
 *
 * The total values are displayed in the same format as the value in the
 * input fields.
 *
 * The total values are calculated by summing all the values in all the
 * .total fields and then formatting the result in the same way as the
 * value in the input fields.
 */

document.querySelectorAll('.total').forEach(element => {
    /**
     * Add event listeners to each element with the class .total
     * to listen for keyup and change events.
     */
    element.addEventListener('keyup', totalKeyUp);
    element.addEventListener('change', totalChange);
});

function totalKeyUp(event) {
    /**
     * Function to handle the keyup event on the .total elements
     * It calls the calculateTotals function to recalculate the total values
     * @param {Event} event The event that triggered this function
     */
    calculateTotals(event);
}

function totalChange(event) {
    /**
     * Function to handle the change event on the .total elements
     * It calls the calculateTotals function to recalculate the total values
     * @param {Event} event The event that triggered this function
     */
    calculateTotals(event);
}

function calculateTotals(event) {
    /**
     * Function to calculate the total amount of money assigned to tags
     * 
     * It takes the current amounts in the form and calculates the total
     * amount of money assigned to the tags, both in the account currency
     * and in the main currency.
     * 
     * It also calculates the total amount of money assigned to the tags
     * in the main currency, taking into account the previous amount assigned
     * to each tag.
     * 
     * @param {Event} event The event that triggered this function
     */

    let totalNow = 0;
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
    /**
     * Add event listeners to each element with the class .remove-btn
     * to listen for click events.
     * 
     * When a button with the class .remove-btn is clicked, it removes the
     * closest tr element and then calls the calculateTotals function to
     * recalculate the total values.
     */
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
