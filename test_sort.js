let classData = {
  "1": 12.5,
  "2": 11.0,
  "3": 13.5,
  "4": 14.0,
  "5": 10.5,
  "6": 15.0
};
let sortedClassLabels = Object.keys(classData).sort((a,b) => {
    let numA = parseInt(a.replace(/\D/g, '')) || 0;
    let numB = parseInt(b.replace(/\D/g, '')) || 0;
    if (numA === numB) return a.localeCompare(b);
    return numA - numB;
});
console.log(sortedClassLabels);
