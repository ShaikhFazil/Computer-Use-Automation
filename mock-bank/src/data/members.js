const tx = (date, desc, amount, kind) => ({ date, desc, amount, kind });

export const MEMBERS = {
  "100200": {
    id: "100200", name: "Ada Lovelace", since: "2016-03-11", status: "Active",
    email: "a.lovelace@example.org", phone: "(415) 555-0138",
    accounts: [
      { number: "SAV-0100200-01", type: "Savings", balance: "$4,210.55", opened: "2016-03-11" },
      { number: "CHK-0100200-02", type: "Checking", balance: "$1,120.00", opened: "2018-07-02" },
    ],
    beneficiaries: [
      { id: "be-01", name: "Charles Babbage", account: "SAV-0088410-01" },
      { id: "be-02", name: "Rent - Oakwood Mgmt", account: "CHK-0142900-04" },
    ],
    transactions: [
      tx("2026-09-14", "Grocery - Whole Foods", "-$86.20", "debit"),
      tx("2026-09-12", "Payroll deposit", "+$2,400.00", "credit"),
      tx("2026-09-09", "Transfer to Babbage", "-$150.00", "debit"),
      tx("2026-09-04", "ATM withdrawal", "-$60.00", "debit"),
      tx("2026-09-01", "Interest", "+$3.11", "credit"),
    ],
  },
  "100355": {
    id: "100355", name: "Grace Hopper", since: "2011-09-01", status: "Active",
    email: "g.hopper@example.org", phone: "(415) 555-0192",
    accounts: [
      { number: "SAV-0100355-01", type: "Savings", balance: "$18,004.10", opened: "2011-09-01" },
      { number: "CHK-0100355-02", type: "Checking", balance: "$3,908.44", opened: "2012-02-15" },
      { number: "MMK-0100355-03", type: "Money Market", balance: "$25,500.00", opened: "2019-06-30" },
    ],
    beneficiaries: [{ id: "be-01", name: "Margaret Hamilton", account: "SAV-0177230-01" }],
    transactions: [
      tx("2026-09-15", "Wire out - vendor", "-$1,200.00", "debit"),
      tx("2026-09-11", "Dividend", "+$412.90", "credit"),
      tx("2026-09-06", "Card - Delta Air", "-$540.30", "debit"),
    ],
  },
  "100412": {
    id: "100412", name: "Alan Turing", since: "2020-01-20", status: "Restricted",
    email: "a.turing@example.org", phone: "(415) 555-0177",
    accounts: [{ number: "SAV-0100412-01", type: "Savings", balance: "$902.34", opened: "2020-01-20" }],
    beneficiaries: [], transactions: [],
  },
  "100487": {
    id: "100487", name: "Katherine Johnson", since: "2014-05-20", status: "Active",
    email: "k.johnson@example.org", phone: "(415) 555-0155",
    accounts: [
      { number: "SAV-0100487-01", type: "Savings", balance: "$7,850.00", opened: "2014-05-20" },
      { number: "CHK-0100487-02", type: "Checking", balance: "$2,300.75", opened: "2015-01-10" },
    ],
    beneficiaries: [
      { id: "be-01", name: "Dorothy Vaughan", account: "SAV-0166500-02" },
      { id: "be-02", name: "NASA Credit Union", account: "CHK-0190030-01" },
    ],
    transactions: [
      tx("2026-09-13", "Utilities - PG&E", "-$140.11", "debit"),
      tx("2026-09-10", "Payroll deposit", "+$3,100.00", "credit"),
      tx("2026-09-02", "Card - Costco", "-$212.48", "debit"),
    ],
  },
  "100521": {
    id: "100521", name: "Margaret Hamilton", since: "2013-11-03", status: "Dormant",
    email: "m.hamilton@example.org", phone: "(415) 555-0121",
    accounts: [{ number: "SAV-0100521-01", type: "Savings", balance: "$512.00", opened: "2013-11-03" }],
    beneficiaries: [], transactions: [tx("2024-02-18", "Card - Shell", "-$40.00", "debit")],
  },
  "100634": {
    id: "100634", name: "Dorothy Vaughan", since: "2010-08-19", status: "Active",
    email: "d.vaughan@example.org", phone: "(415) 555-0143",
    accounts: [
      { number: "SAV-0100634-01", type: "Savings", balance: "$32,110.90", opened: "2010-08-19" },
      { number: "CHK-0100634-02", type: "Checking", balance: "$5,640.20", opened: "2010-08-19" },
    ],
    beneficiaries: [{ id: "be-01", name: "Katherine Johnson", account: "SAV-0100487-01" }],
    transactions: [
      tx("2026-09-16", "Mortgage", "-$2,100.00", "debit"),
      tx("2026-09-10", "Payroll deposit", "+$4,050.00", "credit"),
    ],
  },
  "100702": {
    id: "100702", name: "Annie Easley", since: "2017-04-27", status: "Active",
    email: "a.easley@example.org", phone: "(415) 555-0166",
    accounts: [
      { number: "SAV-0100702-01", type: "Savings", balance: "$1,043.77", opened: "2017-04-27" },
      { number: "CHK-0100702-02", type: "Checking", balance: "$88.10", opened: "2017-04-27" },
    ],
    beneficiaries: [],
    transactions: [
      tx("2026-09-14", "Card - Target", "-$61.99", "debit"),
      tx("2026-09-08", "Refund - Amazon", "+$24.50", "credit"),
    ],
  },
  "100815": {
    id: "100815", name: "Mary Jackson", since: "2012-12-12", status: "Active",
    email: "m.jackson@example.org", phone: "(415) 555-0110",
    accounts: [{ number: "SAV-0100815-01", type: "Savings", balance: "$9,320.00", opened: "2012-12-12" }],
    beneficiaries: [{ id: "be-01", name: "City of Hampton", account: "CHK-0200145-07" }],
    transactions: [
      tx("2026-09-12", "Property tax", "-$780.00", "debit"),
      tx("2026-09-05", "Payroll deposit", "+$2,780.00", "credit"),
    ],
  },
  "100933": {
    id: "100933", name: "Radia Perlman", since: "2015-07-07", status: "Active",
    email: "r.perlman@example.org", phone: "(415) 555-0188",
    accounts: [
      { number: "SAV-0100933-01", type: "Savings", balance: "$14,777.42", opened: "2015-07-07" },
      { number: "CHK-0100933-02", type: "Checking", balance: "$1,905.63", opened: "2016-03-01" },
    ],
    beneficiaries: [
      { id: "be-01", name: "Vint Cerf", account: "SAV-0211900-01" },
      { id: "be-02", name: "Bob Kahn", account: "CHK-0212055-02" },
    ],
    transactions: [
      tx("2026-09-15", "Card - Uniqlo", "-$96.40", "debit"),
      tx("2026-09-09", "Payroll deposit", "+$3,600.00", "credit"),
      tx("2026-09-03", "Transfer to Cerf", "-$500.00", "debit"),
    ],
  },
  "101044": {
    id: "101044", name: "Shafi Goldwasser", since: "2018-10-10", status: "Active",
    email: "s.goldwasser@example.org", phone: "(415) 555-0134",
    accounts: [
      { number: "SAV-0101044-01", type: "Savings", balance: "$6,600.00", opened: "2018-10-10" },
      { number: "MMK-0101044-02", type: "Money Market", balance: "$40,000.00", opened: "2021-01-05" },
    ],
    beneficiaries: [],
    transactions: [tx("2026-09-11", "Dividend", "+$980.00", "credit")],
  },
  "101158": {
    id: "101158", name: "Barbara Liskov", since: "2009-05-14", status: "Active",
    email: "b.liskov@example.org", phone: "(415) 555-0129",
    accounts: [
      { number: "SAV-0101158-01", type: "Savings", balance: "$21,309.18", opened: "2009-05-14" },
      { number: "CHK-0101158-02", type: "Checking", balance: "$4,120.00", opened: "2009-05-14" },
    ],
    beneficiaries: [{ id: "be-01", name: "MIT Federal", account: "CHK-0230011-01" }],
    transactions: [
      tx("2026-09-13", "Tuition", "-$1,500.00", "debit"),
      tx("2026-09-07", "Payroll deposit", "+$5,200.00", "credit"),
    ],
  },
  "101267": {
    id: "101267", name: "Frances Allen", since: "2011-02-28", status: "Restricted",
    email: "f.allen@example.org", phone: "(415) 555-0102",
    accounts: [{ number: "SAV-0101267-01", type: "Savings", balance: "$3,004.00", opened: "2011-02-28" }],
    beneficiaries: [], transactions: [],
  },
  "101390": {
    id: "101390", name: "Karen Sparck Jones", since: "2016-06-06", status: "Active",
    email: "k.sparckjones@example.org", phone: "(415) 555-0176",
    accounts: [
      { number: "SAV-0101390-01", type: "Savings", balance: "$5,125.55", opened: "2016-06-06" },
      { number: "CHK-0101390-02", type: "Checking", balance: "$742.19", opened: "2016-06-06" },
    ],
    beneficiaries: [{ id: "be-01", name: "Cambridge Utilities", account: "CHK-0240880-03" }],
    transactions: [
      tx("2026-09-14", "Card - Waterstones", "-$38.00", "debit"),
      tx("2026-09-06", "Payroll deposit", "+$2,950.00", "credit"),
    ],
  },
};

export const MEMBER_LIST = Object.values(MEMBERS).map((m) => ({
  id: m.id, name: m.name, status: m.status, accounts: m.accounts.length,
}));

export function findMember(id) {
  return MEMBERS[String(id ?? "").trim()] || null;
}

export function savingsOf(member) {
  return member?.accounts.find((a) => a.type === "Savings") || null;
}
