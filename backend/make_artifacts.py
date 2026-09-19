"""Author the committed capability artifacts from the schema types (guarantees
validity). These are the reviewable contracts an agent invokes by name."""
from cua.schema import (
    CapabilityArtifact, SurfaceBinding, InputParam, OutputField, ParamType,
    Step, ActionType, Reversibility, ElementTarget, Locator, LocatorStrategy,
    Checkpoint, CheckpointKind, BusinessOutcome, ApprovalState,
    TenantOverride, StepLocatorOverride,
)
from cua.catalog import Catalog

def L(strategy, value, role=None):
    return Locator(strategy=strategy, value=value, role=role)

def target(desc, locators, note=""):
    return ElementTarget(description=desc, locators=locators, robustness_note=note)

cat = Catalog()

member_id_field = target("Member ID search box", [
    L(LocatorStrategy.ROLE_NAME, "Member ID", role="textbox"),
    L(LocatorStrategy.LABEL, "Member ID"),
    L(LocatorStrategy.TEST_ID, "member-id-input"),
    L(LocatorStrategy.PLACEHOLDER, "e.g. 100200"),
], "Prefer accessible role+name/label; test-id and placeholder are fallbacks.")

search_btn = target("Search button", [
    L(LocatorStrategy.ROLE_NAME, "Search", role="button"),
    L(LocatorStrategy.TEST_ID, "search-btn"),
    L(LocatorStrategy.TEXT, "Search"),
], "Role+name is stable across markup changes.")

savings_value = target("Savings balance value", [
    L(LocatorStrategy.LABEL, "Savings balance"),
    L(LocatorStrategy.TEST_ID, "savings-balance"),
], "aria-label carries the semantic name; test-id is the fallback.")

lookup = CapabilityArtifact(
    name="member_savings_lookup", version="1.1.0",
    title="Look up a member's savings balance",
    description="Given a member ID, open the servicing record and read the savings balance. Read-only.",
    goal="Find the savings account balance for a given member ID in the servicing console.",
    binding=SurfaceBinding(kind="web", app="mock_bank", vendor="meridian_servicing",
                           version="1.x", base_url_param="base_url", tenant=None),
    inputs=[
        InputParam(name="base_url", type=ParamType.STRING, required=True,
                   description="Entry URL of the console.", example="http://localhost:5173/"),
        InputParam(name="member_id", type=ParamType.STRING, required=True,
                   description="The member's numeric ID.", example="100200"),
    ],
    outputs=[OutputField(name="savings_balance", type=ParamType.STRING,
                         description="The member's savings balance, as displayed.")],
    steps=[
        Step(index=0, action=ActionType.NAVIGATE, value="{{base_url}}",
             reversibility=Reversibility.SAFE, note="Open the console home.",
             checkpoint=Checkpoint(kind=CheckpointKind.ELEMENT_VISIBLE, target=member_id_field,
                                   description="Lookup form is visible.")),
        Step(index=1, action=ActionType.TYPE, target=member_id_field, value="{{member_id}}",
             reversibility=Reversibility.SAFE, note="Enter the member ID."),
        Step(index=2, action=ActionType.CLICK, target=search_btn,
             reversibility=Reversibility.SAFE, note="Submit the lookup.",
             checkpoint=Checkpoint(kind=CheckpointKind.URL_MATCHES, expected="/member/",
                                   description="Navigated to a member record.")),
        Step(index=3, action=ActionType.EXTRACT, target=savings_value, output_key="savings_balance",
             reversibility=Reversibility.SAFE, note="Read the savings balance.",
             checkpoint=Checkpoint(kind=CheckpointKind.ELEMENT_VISIBLE, target=savings_value,
                                   description="Savings balance is on screen.")),
    ],
    success=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="Savings balance",
                       description="Member record with a savings balance is shown."),
    business_outcomes=[
        BusinessOutcome(code="member_not_found", description="No member matches the given ID.",
                        detect=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="No member found")),
        BusinessOutcome(code="permission_denied", description="Record is restricted.",
                        detect=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="Access restricted")),
    ],
    approval=ApprovalState.APPROVED,
    overrides={
        "westside_cu": TenantOverride(
            tenant="westside_cu", note="Westside CU relabels the primary action 'Find'.",
            step_locator_overrides=[StepLocatorOverride(step_index=2, locators=[
                L(LocatorStrategy.ROLE_NAME, "Find", role="button"),
                L(LocatorStrategy.TEXT, "Find"),
            ])],
        )
    },
)
print("saved:", cat.save(lookup).name, lookup.version, "| overrides:", list(lookup.overrides))

# --------------------------------------------------------------------------- #
# 2. open_sub_account — multi-field form + confirmation + RISKY confirm
# --------------------------------------------------------------------------- #
open_btn = target("Open sub-account button", [
    L(LocatorStrategy.ROLE_NAME, "Open sub-account", role="button"),
    L(LocatorStrategy.TEST_ID, "open-sub-account"),
])
acct_type = target("Account type select", [
    L(LocatorStrategy.LABEL, "Account type"), L(LocatorStrategy.TEST_ID, "account-type"),
])
deposit = target("Initial deposit", [
    L(LocatorStrategy.LABEL, "Initial deposit (optional)"), L(LocatorStrategy.TEST_ID, "initial-deposit"),
])
review_btn = target("Review button", [
    L(LocatorStrategy.ROLE_NAME, "Review", role="button"), L(LocatorStrategy.TEST_ID, "review-btn"),
])
confirm_btn = target("Confirm button", [
    L(LocatorStrategy.ROLE_NAME, "Confirm", role="button"), L(LocatorStrategy.TEST_ID, "confirm-btn"),
])

sub = CapabilityArtifact(
    name="open_sub_account", version="1.0.0",
    title="Open a sub-account for a member",
    description="Fill the new sub-account form, reach the confirmation screen, and open the account. The final confirmation is irreversible.",
    goal="Open a new sub-account for a member and complete the confirmation.",
    binding=SurfaceBinding(kind="web", app="mock_bank", vendor="meridian_servicing",
                           version="1.x", base_url_param="base_url", tenant=None),
    inputs=[
        InputParam(name="base_url", type=ParamType.STRING, required=True, example="http://localhost:5173/"),
        InputParam(name="member_id", type=ParamType.STRING, required=True, example="100200"),
        InputParam(name="account_type", type=ParamType.STRING, required=False, example="Savings"),
        InputParam(name="initial_deposit", type=ParamType.STRING, required=False, example="100.00"),
    ],
    outputs=[OutputField(name="result", type=ParamType.STRING, description="Outcome text after confirming.")],
    steps=[
        Step(index=0, action=ActionType.NAVIGATE, value="{{base_url}}member/{{member_id}}",
             reversibility=Reversibility.SAFE, note="Open the member record.",
             checkpoint=Checkpoint(kind=CheckpointKind.ELEMENT_VISIBLE, target=open_btn,
                                   description="Member record is open.")),
        Step(index=1, action=ActionType.CLICK, target=open_btn, reversibility=Reversibility.SAFE,
             note="Start the new sub-account flow.",
             checkpoint=Checkpoint(kind=CheckpointKind.ELEMENT_VISIBLE, target=acct_type,
                                   description="Sub-account form is visible.")),
        Step(index=2, action=ActionType.SELECT, target=acct_type, value="{{account_type}}",
             reversibility=Reversibility.SAFE, note="Choose the account type."),
        Step(index=3, action=ActionType.TYPE, target=deposit, value="{{initial_deposit}}",
             reversibility=Reversibility.SAFE, note="Enter the initial deposit."),
        Step(index=4, action=ActionType.CLICK, target=review_btn, reversibility=Reversibility.SAFE,
             note="Go to the confirmation screen.",
             checkpoint=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="Confirmation",
                                   description="Confirmation screen reached.")),
        Step(index=5, action=ActionType.CLICK, target=confirm_btn, reversibility=Reversibility.RISKY,
             note="Open the account. Irreversible — gated by policy.",
             checkpoint=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="Sub-account opened",
                                   description="Account was opened.")),
    ],
    success=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="Sub-account opened",
                       description="The sub-account was opened."),
    business_outcomes=[
        BusinessOutcome(code="member_not_found", description="No member matches the given ID.",
                        detect=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="No member found")),
    ],
    approval=ApprovalState.APPROVED,
)
print("saved:", cat.save(sub).name, sub.version)

# --------------------------------------------------------------------------- #
# 3. transfer_funds — multi-field form + confirmation + RISKY confirm
# --------------------------------------------------------------------------- #
transfer_btn = target("Transfer funds button", [
    L(LocatorStrategy.ROLE_NAME, "Transfer funds", role="button"),
    L(LocatorStrategy.TEST_ID, "transfer-funds"),
])
from_acct = target("From account select", [
    L(LocatorStrategy.LABEL, "From account"), L(LocatorStrategy.TEST_ID, "from-account"),
])
beneficiary = target("Beneficiary select", [
    L(LocatorStrategy.LABEL, "Beneficiary"), L(LocatorStrategy.TEST_ID, "beneficiary"),
])
amount = target("Amount", [
    L(LocatorStrategy.LABEL, "Amount (USD)"), L(LocatorStrategy.TEST_ID, "amount"),
])
review_transfer = target("Review transfer button", [
    L(LocatorStrategy.ROLE_NAME, "Review transfer", role="button"), L(LocatorStrategy.TEST_ID, "review-transfer"),
])
confirm_transfer = target("Confirm transfer button", [
    L(LocatorStrategy.ROLE_NAME, "Confirm transfer", role="button"), L(LocatorStrategy.TEST_ID, "confirm-transfer"),
])

transfer = CapabilityArtifact(
    name="transfer_funds", version="1.0.0",
    title="Transfer funds to a saved beneficiary",
    description="Complete the multi-field transfer form, review, and submit. Submitting the transfer is irreversible.",
    goal="Transfer an amount from a member's account to a saved beneficiary.",
    binding=SurfaceBinding(kind="web", app="mock_bank", vendor="meridian_servicing",
                           version="1.x", base_url_param="base_url", tenant=None),
    inputs=[
        InputParam(name="base_url", type=ParamType.STRING, required=True, example="http://localhost:5173/"),
        InputParam(name="member_id", type=ParamType.STRING, required=True, example="100200"),
        InputParam(name="from_account", type=ParamType.STRING, required=True, example="SAV-0100200-01"),
        InputParam(name="beneficiary", type=ParamType.STRING, required=True, example="Charles Babbage"),
        InputParam(name="amount", type=ParamType.STRING, required=True, example="250.00"),
        InputParam(name="memo", type=ParamType.STRING, required=False, sensitive=False, example="September rent"),
    ],
    outputs=[OutputField(name="result", type=ParamType.STRING, description="Outcome text after submitting.")],
    steps=[
        Step(index=0, action=ActionType.NAVIGATE, value="{{base_url}}member/{{member_id}}/transfer/new",
             reversibility=Reversibility.SAFE, note="Open the transfer form.",
             checkpoint=Checkpoint(kind=CheckpointKind.ELEMENT_VISIBLE, target=from_acct,
                                   description="Transfer form is visible.")),
        Step(index=1, action=ActionType.SELECT, target=from_acct, value="{{from_account}}",
             reversibility=Reversibility.SAFE, note="Choose the source account."),
        Step(index=2, action=ActionType.SELECT, target=beneficiary, value="{{beneficiary}}",
             reversibility=Reversibility.SAFE, note="Choose the beneficiary."),
        Step(index=3, action=ActionType.TYPE, target=amount, value="{{amount}}",
             reversibility=Reversibility.SAFE, note="Enter the amount."),
        Step(index=4, action=ActionType.CLICK, target=review_transfer, reversibility=Reversibility.SAFE,
             note="Go to review.",
             checkpoint=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="Confirm transfer",
                                   description="Review screen reached.")),
        Step(index=5, action=ActionType.CLICK, target=confirm_transfer, reversibility=Reversibility.RISKY,
             note="Submit the transfer. Irreversible — gated by policy.",
             checkpoint=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="Transfer submitted",
                                   description="Transfer was submitted.")),
    ],
    success=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="Transfer submitted",
                       description="The transfer was submitted."),
    business_outcomes=[
        BusinessOutcome(code="member_not_found", description="No member matches the given ID.",
                        detect=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="No member found")),
    ],
    approval=ApprovalState.APPROVED,
)
print("saved:", cat.save(transfer).name, transfer.version)
print("\nCatalog now:", [a["name"] for a in cat.list()])
