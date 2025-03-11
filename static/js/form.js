uploadField = document.getElementById("id_voucher");

uploadField.onchange = function() {
    if(this.files[0].size > 0.5*1024*1024) {
       alert("File should not exceed 0.5 MiB!");
       this.value = "";
    }
};

balanceField = document.getElementById("id_current_balance");
amountField = document.getElementById("id_amount");
typeField = document.getElementById("id_transaction_type");
hold = document.getElementById("id_hold");

function updateFinalBalance() {
    const currentBalance = parseFloat(document.getElementById("current_balance").textContent);
    const previousAmount = parseFloat(document.getElementsByName("previous-amount")[0].value);
    const previousType = document.getElementsByName("previous-type")[0].value;
    const amount = parseFloat(amountField.value);

    if (amount && typeField.value && !hold.checked) {
        let newBalance = currentBalance;
        if (!isNaN(previousAmount) && previousType) {
            if (previousType == '+') {
                newBalance -= previousAmount;
            } else {
                newBalance += previousAmount;
            }
        }
        newBalance += (typeField.value == '+' ? amount : -amount);

        document.getElementById("final_balance").textContent = `${newBalance.toFixed(2)}`;
    } else {
        document.getElementById("final_balance").textContent = `${currentBalance.toFixed(2)}`;
    }
}

amountField.addEventListener('keyup', function(e) {
    // Remove any non-numeric characters
    this.value = this.value.replace(/[.,e]/g, '');

    // Format as a bank amount by dividing by 100
    if (this.value) {
        const numericValue = parseFloat(this.value) / 100;
        this.value = numericValue.toFixed(2);
    }
});

amountField.onkeyup = updateFinalBalance;
amountField.onchange = updateFinalBalance;
typeField.onchange = updateFinalBalance;
hold.onchange = updateFinalBalance;