# Single Responsibility Principle

[All programming principles](../SKILL.md)

**Definition:** Give a module responsibility for one coherent source of change:
one business function or closely aligned group of stakeholders. Keep changes
driven by that responsibility together, and isolate independently driven
responsibilities. A responsibility can involve several operations; counting
methods or interpreting every edit as a new responsibility is misleading.

## Example 1: payroll calculation and document layout

**Circumstance:** Payroll specialists change overtime rules. The communications
team changes the payslip's logo and layout.

```text
Bad: employee_service.py owns both sources of change.
  calculate_pay(hours, contract)
  draw_payslip_logo(canvas)
  position_payslip_columns(canvas)

Good: each responsibility has its own module.
  payroll.py:    calculate_pay(hours, contract) -> pay breakdown
  payslip.py:    render_payslip(pay_breakdown) -> document
```

A logo change should not require understanding overtime calculations. A change
to pay categories can legitimately affect both sides' shared contract; SRP does
not promise that every future change touches exactly one file.

## Example 2: several operations can share one responsibility

**Circumstance:** One packaging policy owns dimension limits, weight limits and
the box chosen from those limits.

| Arrangement | Assessment |
| --- | --- |
| **Good:** `packaging.py` contains dimension checks, weight checks and box selection. | Several operations cooperate to implement one packaging policy. |
| **Worse:** Put every check in a separate service and pass a mutable context between them. | The same responsibility is scattered, and callers must know the correct preparation order. |
| **Better after a real change:** Customs declarations become independently owned and change under a separate regulatory process. | Introduce a customs boundary with its own contract; retain the cohesive packaging policy. |

SRP focuses on why changes arrive. Cohesion asks whether the contents form a
coherent unit. They support one another but ask different diagnostic questions.

**Review question:** Who requests changes to this module, and are their reasons
independent enough that one change should not endanger the other behaviour?

## References

Robert C. Martin, [The Single Responsibility Principle](https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html).
