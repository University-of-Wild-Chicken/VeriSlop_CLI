import VSCore3
import VSCore3.SourceFacts
import VeriSlopContract

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeGoal

/-- Supervisor goal vscore.reference_refinement/0.3; exact delivered bytes sha256:e7d916f8c9e45a0b1901433aa80e3cf36b73942ff6aaba41a0bfc088ff68a51c. -/
def sourceBytes : List Nat := [123, 34, 100, 101, 99, 108, 97, 114, 97, 116, 105, 111, 110, 115, 34, 58, 91, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 115, 104, 97, 100, 101, 34, 44, 34, 116, 121, 112, 101, 34, 58, 123, 34, 101, 110, 117, 109, 34, 58, 34, 83, 104, 97, 100, 101, 34, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 110, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 110, 97, 116, 34, 125, 93, 44, 34, 105, 100, 34, 58, 34, 80, 97, 114, 99, 101, 108, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 44, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 112, 97, 114, 99, 101, 108, 34, 44, 34, 116, 121, 112, 101, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 114, 99, 101, 108, 34, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 97, 99, 116, 105, 118, 101, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 98, 111, 111, 108, 34, 125, 93, 44, 34, 105, 100, 34, 58, 34, 69, 110, 118, 101, 108, 111, 112, 101, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 93, 44, 34, 101, 110, 116, 114, 105, 101, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 97, 114, 103, 115, 34, 58, 91, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 34, 58, 34, 115, 104, 105, 102, 116, 69, 110, 118, 101, 108, 111, 112, 101, 34, 44, 34, 116, 97, 103, 34, 58, 34, 99, 97, 108, 108, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 109, 97, 112, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 105, 100, 34, 58, 34, 115, 104, 105, 102, 116, 69, 110, 118, 101, 108, 111, 112, 101, 115, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 69, 110, 118, 101, 108, 111, 112, 101, 34, 125, 125, 44, 34, 110, 97, 116, 34, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 69, 110, 118, 101, 108, 111, 112, 101, 34, 125, 125, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 97, 114, 103, 115, 34, 58, 91, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 34, 58, 34, 107, 101, 101, 112, 69, 110, 118, 101, 108, 111, 112, 101, 34, 44, 34, 116, 97, 103, 34, 58, 34, 99, 97, 108, 108, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 102, 105, 108, 116, 101, 114, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 105, 100, 34, 58, 34, 107, 101, 101, 112, 80, 97, 114, 99, 101, 108, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 69, 110, 118, 101, 108, 111, 112, 101, 34, 125, 125, 44, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 114, 99, 101, 108, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 69, 110, 118, 101, 108, 111, 112, 101, 34, 125, 125, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 105, 110, 105, 116, 105, 97, 108, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 115, 111, 117, 114, 99, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 50, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 115, 116, 101, 112, 34, 58, 123, 34, 97, 114, 103, 115, 34, 58, 91, 123, 34, 105, 110, 100, 101, 120, 34, 58, 50, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 34, 58, 34, 116, 111, 116, 97, 108, 83, 116, 101, 112, 34, 44, 34, 116, 97, 103, 34, 58, 34, 99, 97, 108, 108, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 102, 111, 108, 100, 34, 125, 44, 34, 105, 100, 34, 58, 34, 115, 104, 97, 100, 101, 84, 111, 116, 97, 108, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 69, 110, 118, 101, 108, 111, 112, 101, 34, 125, 125, 44, 34, 110, 97, 116, 34, 44, 123, 34, 101, 110, 117, 109, 34, 58, 34, 83, 104, 97, 100, 101, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 110, 97, 116, 34, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 101, 113, 34, 125, 44, 34, 105, 100, 34, 58, 34, 115, 97, 109, 101, 83, 104, 97, 100, 101, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 101, 110, 117, 109, 34, 58, 34, 83, 104, 97, 100, 101, 34, 125, 44, 123, 34, 101, 110, 117, 109, 34, 58, 34, 83, 104, 97, 100, 101, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 98, 111, 111, 108, 34, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 110, 97, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 34, 48, 34, 125, 44, 34, 105, 100, 34, 58, 34, 105, 110, 115, 112, 101, 99, 116, 69, 110, 118, 101, 108, 111, 112, 101, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 69, 110, 118, 101, 108, 111, 112, 101, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 110, 97, 116, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 115, 104, 97, 100, 101, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 115, 104, 97, 100, 101, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 110, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 110, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 125, 93, 44, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 114, 99, 101, 108, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 44, 34, 105, 100, 34, 58, 34, 115, 104, 105, 102, 116, 80, 97, 114, 99, 101, 108, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 110, 97, 116, 34, 44, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 114, 99, 101, 108, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 114, 99, 101, 108, 34, 125, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 112, 97, 114, 99, 101, 108, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 97, 114, 103, 115, 34, 58, 91, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 112, 97, 114, 99, 101, 108, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 34, 58, 34, 115, 104, 105, 102, 116, 80, 97, 114, 99, 101, 108, 34, 44, 34, 116, 97, 103, 34, 58, 34, 99, 97, 108, 108, 34, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 97, 99, 116, 105, 118, 101, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 99, 116, 105, 118, 101, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 93, 44, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 69, 110, 118, 101, 108, 111, 112, 101, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 44, 34, 105, 100, 34, 58, 34, 115, 104, 105, 102, 116, 69, 110, 118, 101, 108, 111, 112, 101, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 110, 97, 116, 34, 44, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 69, 110, 118, 101, 108, 111, 112, 101, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 69, 110, 118, 101, 108, 111, 112, 101, 34, 125, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 112, 97, 114, 99, 101, 108, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 101, 113, 34, 125, 44, 34, 105, 100, 34, 58, 34, 107, 101, 101, 112, 69, 110, 118, 101, 108, 111, 112, 101, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 114, 99, 101, 108, 34, 125, 44, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 69, 110, 118, 101, 108, 111, 112, 101, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 98, 111, 111, 108, 34, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 99, 111, 110, 100, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 115, 104, 97, 100, 101, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 112, 97, 114, 99, 101, 108, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 50, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 101, 113, 34, 125, 44, 34, 101, 108, 115, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 105, 102, 34, 44, 34, 116, 104, 101, 110, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 110, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 112, 97, 114, 99, 101, 108, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 125, 44, 34, 105, 100, 34, 58, 34, 116, 111, 116, 97, 108, 83, 116, 101, 112, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 101, 110, 117, 109, 34, 58, 34, 83, 104, 97, 100, 101, 34, 125, 44, 34, 110, 97, 116, 34, 44, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 69, 110, 118, 101, 108, 111, 112, 101, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 110, 97, 116, 34, 125, 93, 44, 34, 108, 97, 110, 103, 117, 97, 103, 101, 34, 58, 34, 118, 115, 99, 111, 114, 101, 47, 48, 46, 51, 34, 44, 34, 112, 114, 111, 102, 105, 108, 101, 34, 58, 34, 100, 97, 116, 97, 45, 112, 105, 112, 101, 108, 105, 110, 101, 47, 48, 46, 51, 34, 125]
def rawProgram : VSCore3.Program := { language := "vscore/0.3", profile := "data-pipeline/0.3", declarations := [(VSCore3.DataDecl.record "Parcel" [("shade", (VSCore3.Ty.enum "Shade")), ("n", VSCore3.Ty.nat)]), (VSCore3.DataDecl.record "Envelope" [("parcel", (VSCore3.Ty.record "Parcel")), ("active", VSCore3.Ty.bool)])], helpers := [{ id := "shiftParcel", params := [VSCore3.Ty.nat, (VSCore3.Ty.record "Parcel")], result := (VSCore3.Ty.record "Parcel"), body := (VSCore3.Expr.record "Parcel" [("shade", (VSCore3.Expr.project (VSCore3.Expr.var 0) "shade")), ("n", (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.project (VSCore3.Expr.var 0) "n") (VSCore3.Expr.var 1)))]) },
{ id := "shiftEnvelope", params := [VSCore3.Ty.nat, (VSCore3.Ty.record "Envelope")], result := (VSCore3.Ty.record "Envelope"), body := (VSCore3.Expr.record "Envelope" [("parcel", (VSCore3.Expr.call "shiftParcel" [(VSCore3.Expr.var 1), (VSCore3.Expr.project (VSCore3.Expr.var 0) "parcel")])), ("active", (VSCore3.Expr.project (VSCore3.Expr.var 0) "active"))]) },
{ id := "keepEnvelope", params := [(VSCore3.Ty.record "Parcel"), (VSCore3.Ty.record "Envelope")], result := VSCore3.Ty.bool, body := (VSCore3.Expr.bin VSCore.BinOp.eq (VSCore3.Expr.project (VSCore3.Expr.var 0) "parcel") (VSCore3.Expr.var 1)) },
{ id := "totalStep", params := [(VSCore3.Ty.enum "Shade"), VSCore3.Ty.nat, (VSCore3.Ty.record "Envelope")], result := VSCore3.Ty.nat, body := (VSCore3.Expr.ite (VSCore3.Expr.bin VSCore.BinOp.eq (VSCore3.Expr.project (VSCore3.Expr.project (VSCore3.Expr.var 0) "parcel") "shade") (VSCore3.Expr.var 2)) (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.var 1) (VSCore3.Expr.project (VSCore3.Expr.project (VSCore3.Expr.var 0) "parcel") "n")) (VSCore3.Expr.var 1)) }], entries := [{ id := "shiftEnvelopes", params := [(VSCore3.Ty.list (VSCore3.Ty.record "Envelope")), VSCore3.Ty.nat], result := (VSCore3.Ty.list (VSCore3.Ty.record "Envelope")), body := (VSCore3.Expr.listMap (VSCore3.Expr.var 1) (VSCore3.Expr.call "shiftEnvelope" [(VSCore3.Expr.var 1), (VSCore3.Expr.var 0)])) },
{ id := "keepParcel", params := [(VSCore3.Ty.list (VSCore3.Ty.record "Envelope")), (VSCore3.Ty.record "Parcel")], result := (VSCore3.Ty.list (VSCore3.Ty.record "Envelope")), body := (VSCore3.Expr.listFilter (VSCore3.Expr.var 1) (VSCore3.Expr.call "keepEnvelope" [(VSCore3.Expr.var 1), (VSCore3.Expr.var 0)])) },
{ id := "shadeTotal", params := [(VSCore3.Ty.list (VSCore3.Ty.record "Envelope")), VSCore3.Ty.nat, (VSCore3.Ty.enum "Shade")], result := VSCore3.Ty.nat, body := (VSCore3.Expr.listFold (VSCore3.Expr.var 2) (VSCore3.Expr.var 1) (VSCore3.Expr.call "totalStep" [(VSCore3.Expr.var 2), (VSCore3.Expr.var 1), (VSCore3.Expr.var 0)])) },
{ id := "sameShade", params := [(VSCore3.Ty.enum "Shade"), (VSCore3.Ty.enum "Shade")], result := VSCore3.Ty.bool, body := (VSCore3.Expr.bin VSCore.BinOp.eq (VSCore3.Expr.var 1) (VSCore3.Expr.var 0)) },
{ id := "inspectEnvelope", params := [(VSCore3.Ty.record "Envelope")], result := VSCore3.Ty.nat, body := (VSCore3.Expr.nat 0) }] }
def profile : VSCore3.Profile := { enums := [("Shade", ["light", "dark", "neutral"])] }
def signatures : List VSCore3.EntrySig := [{ id := "shiftEnvelopes", params := [(VSCore3.Ty.list (VSCore3.Ty.record "Envelope")), VSCore3.Ty.nat], result := (VSCore3.Ty.list (VSCore3.Ty.record "Envelope")) },
  { id := "keepParcel", params := [(VSCore3.Ty.list (VSCore3.Ty.record "Envelope")), (VSCore3.Ty.record "Parcel")], result := (VSCore3.Ty.list (VSCore3.Ty.record "Envelope")) },
  { id := "shadeTotal", params := [(VSCore3.Ty.list (VSCore3.Ty.record "Envelope")), VSCore3.Ty.nat, (VSCore3.Ty.enum "Shade")], result := VSCore3.Ty.nat },
  { id := "sameShade", params := [(VSCore3.Ty.enum "Shade"), (VSCore3.Ty.enum "Shade")], result := VSCore3.Ty.bool },
  { id := "inspectEnvelope", params := [(VSCore3.Ty.record "Envelope")], result := VSCore3.Ty.nat }]
def SourceParses : Prop := VSCore3.parseSource sourceBytes = .ok rawProgram
theorem source_parses : SourceParses := by rfl
def SourceChecks : Prop := VSCore3.checkProgram profile rawProgram = .ok signatures
theorem source_checks : SourceChecks := VSCore3.checkProgram_of_check (by decide +kernel)
def checkedProgram : VSCore3.CheckedProgram := (VSCore3.compileProgram profile rawProgram).toOption.getD
  { declarations := [], helpers := [], entries := [], signatures := [] }
theorem compiled_ok : VSCore3.compileProgram profile rawProgram = .ok checkedProgram := by with_unfolding_all rfl

/-- Exact accepted carrier {"enum":"Shade"}. -/
def adapter_0 : VSCore3.Adapter (.enum "Shade" ["light", "dark", "neutral"]) @VeriSlopAST.Shade :=
  { to := fun x => match x with | VeriSlopAST.Shade.light => ⟨"light", by decide +kernel⟩ | VeriSlopAST.Shade.dark => ⟨"dark", by decide +kernel⟩ | VeriSlopAST.Shade.neutral => ⟨"neutral", by decide +kernel⟩
    inv := fun x => if x.val = "light" then @VeriSlopAST.Shade.light else if x.val = "dark" then @VeriSlopAST.Shade.dark else @VeriSlopAST.Shade.neutral
    from_to := by intro x; cases x <;> rfl
    to_from := by intro x; rcases x with ⟨x, h⟩; simp only [List.mem_cons, List.not_mem_nil, or_false] at h; rcases h with rfl | rfl | rfl; all_goals rfl }
def adapter_0_raw : VSCore3.RawLaws (.enum "Shade" ["light", "dark", "neutral"]) := (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"])
theorem adapter_0_decode_encode (x : @VeriSlopAST.Shade) :
    VSCore3.decode (.enum "Shade" ["light", "dark", "neutral"]) (adapter_0.encode x) = some (adapter_0.to x) :=
  adapter_0.decode_encode adapter_0_raw x

/-- Exact accepted carrier "Nat". -/
def adapter_1 : VSCore3.Adapter .nat @Nat :=
  VSCore3.natAdapter
def adapter_1_raw : VSCore3.RawLaws .nat := VSCore3.natRawLaws
theorem adapter_1_decode_encode (x : @Nat) :
    VSCore3.decode .nat (adapter_1.encode x) = some (adapter_1.to x) :=
  adapter_1.decode_encode adapter_1_raw x

/-- Exact accepted carrier {"record":"Parcel"}. -/
def adapter_2 : VSCore3.Adapter (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) @VeriSlopAST.Parcel :=
  { to := fun x => (adapter_0.to (@VeriSlopAST.Parcel.shade x), (adapter_1.to (@VeriSlopAST.Parcel.n x), ()))
    inv := fun x => @VeriSlopAST.Parcel.mk (adapter_0.inv (x.1)) (adapter_1.inv (x.2.1))
    from_to := by intro x; cases x; simp [adapter_0.from_to, adapter_1.from_to]
    to_from := by intro x; rcases x with ⟨x0, x⟩; rcases x with ⟨x1, x⟩; cases x; simp [adapter_0.to_from, adapter_1.to_from] }
def adapter_2_raw : VSCore3.RawLaws (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) := (VSCore3.recordRawLaws "Parcel" (VSCore3.RecordLayout.cons "shade" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws)))
theorem adapter_2_decode_encode (x : @VeriSlopAST.Parcel) :
    VSCore3.decode (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (adapter_2.encode x) = some (adapter_2.to x) :=
  adapter_2.decode_encode adapter_2_raw x

/-- Exact accepted carrier "Bool". -/
def adapter_3 : VSCore3.Adapter .bool @Bool :=
  VSCore3.boolAdapter
def adapter_3_raw : VSCore3.RawLaws .bool := VSCore3.boolRawLaws
theorem adapter_3_decode_encode (x : @Bool) :
    VSCore3.decode .bool (adapter_3.encode x) = some (adapter_3.to x) :=
  adapter_3.decode_encode adapter_3_raw x

/-- Exact accepted carrier {"record":"Envelope"}. -/
def adapter_4 : VSCore3.Adapter (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))) @VeriSlopAST.Envelope :=
  { to := fun x => (adapter_2.to (@VeriSlopAST.Envelope.parcel x), (adapter_3.to (@VeriSlopAST.Envelope.active x), ()))
    inv := fun x => @VeriSlopAST.Envelope.mk (adapter_2.inv (x.1)) (adapter_3.inv (x.2.1))
    from_to := by intro x; cases x; simp [adapter_2.from_to, adapter_3.from_to]
    to_from := by intro x; rcases x with ⟨x0, x⟩; rcases x with ⟨x1, x⟩; cases x; simp [adapter_2.to_from, adapter_3.to_from] }
def adapter_4_raw : VSCore3.RawLaws (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))) := (VSCore3.recordRawLaws "Envelope" (VSCore3.RecordLayout.cons "parcel" (VSCore3.RecordLayout.cons "active" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Parcel" (VSCore3.RecordLayout.cons "shade" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws)))
theorem adapter_4_decode_encode (x : @VeriSlopAST.Envelope) :
    VSCore3.decode (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))) (adapter_4.encode x) = some (adapter_4.to x) :=
  adapter_4.decode_encode adapter_4_raw x

/-- Exact accepted carrier {"list":{"record":"Envelope"}}. -/
def adapter_5 : VSCore3.Adapter (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) (@List.{0} @VeriSlopAST.Envelope) :=
  VSCore3.listAdapter adapter_4
def adapter_5_raw : VSCore3.RawLaws (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) := (VSCore3.listRawLaws (VSCore3.recordRawLaws "Envelope" (VSCore3.RecordLayout.cons "parcel" (VSCore3.RecordLayout.cons "active" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Parcel" (VSCore3.RecordLayout.cons "shade" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws))))
theorem adapter_5_decode_encode (x : (@List.{0} @VeriSlopAST.Envelope)) :
    VSCore3.decode (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) (adapter_5.encode x) = some (adapter_5.to x) :=
  adapter_5.decode_encode adapter_5_raw x

abbrev entry_inspectEnvelope : VSCore3.CompiledFunction :=
  { id := "inspectEnvelope", params := [(.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))], result := .nat,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "inspectEnvelope").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_inspectEnvelope : VSCore3.findEntry checkedProgram "inspectEnvelope" = some entry_inspectEnvelope := by with_unfolding_all rfl
def source_fn_inspectEnvelope (x__0 : @VeriSlopAST.Envelope) : @Nat := by
  with_unfolding_all exact adapter_1.inv (entry_inspectEnvelope.run (adapter_4.to x__0, ()))
def Refines_inspectEnvelope : Prop := (∀ (x__0 : @VeriSlopAST.Envelope), (@Eq.{1} @Nat (@VeriSlopBridgeGoal.source_fn_inspectEnvelope x__0) (@VeriSlopAST.inspectEnvelope x__0)))
def RawEval_inspectEnvelope : Prop := ∀ (x__0 : @VeriSlopAST.Envelope),
  VSCore3.evalEntry profile rawProgram "inspectEnvelope" [adapter_4.encode x__0] =
    .ok (adapter_1.encode (source_fn_inspectEnvelope x__0))
theorem raw_eval_inspectEnvelope : RawEval_inspectEnvelope := by
  with_unfolding_all
    intro x__0
    have hd : VSCore3.decodeEnv entry_inspectEnvelope.params [adapter_4.encode x__0] = some (adapter_4.to x__0, ()) := by
      change VSCore3.decodeEnv [(.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))] [adapter_4.encode x__0] = some (adapter_4.to x__0, ())
      simp only [VSCore3.decodeEnv, adapter_4_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "inspectEnvelope" [adapter_4.encode x__0] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_inspectEnvelope, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_inspectEnvelope, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .nat (entry_inspectEnvelope.run (adapter_4.to x__0, ()))) =
      Except.ok (VSCore3.encode .nat (adapter_1.to (adapter_1.inv (entry_inspectEnvelope.run (adapter_4.to x__0, ())))))
    rw [adapter_1.to_from]
def InputsCover_inspectEnvelope : Prop := ∀ args, VSCore3.ArgsTyped entry_inspectEnvelope args → ∃ (x__0 : @VeriSlopAST.Envelope), args = [adapter_4.encode x__0]
theorem inputs_cover_inspectEnvelope : InputsCover_inspectEnvelope := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [(.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [(.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact (VSCore3.recordRawLaws "Envelope" (VSCore3.RecordLayout.cons "parcel" (VSCore3.RecordLayout.cons "active" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Parcel" (VSCore3.RecordLayout.cons "shade" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws)))) args env hd
    rcases env with ⟨v__0, env⟩
    cases env
    refine ⟨adapter_4.inv v__0, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_4.to_from] using he.symm

def sourceFacts_inspectEnvelope : VeriSlop.Source.ModuleFacts :=
  let m := VSCore3.exactSourceFacts profile rawProgram "inspectEnvelope"
  { entries := m.entries.map (fun e => ⟨e.file, e.id, e.arity⟩),
    uniqueEntries := m.uniqueEntries, typedTotal := m.typedTotal, deterministic := m.deterministic,
    inputPreserved := m.inputPreserved, noExternalIO := m.noExternalIO,
    noFloatingPoint := m.noFloatingPoint, pureData := m.pureData,
    restrictedRuntimeOnly := m.restrictedRuntimeOnly }
def SourceAdequate_inspectEnvelope : Prop :=
  VSCore3.SourceFactsAdequate profile rawProgram "inspectEnvelope" checkedProgram entry_inspectEnvelope
theorem source_adequate_inspectEnvelope : SourceAdequate_inspectEnvelope := by
  with_unfolding_all
    exact VSCore3.exactSourceFacts_adequate compiled_ok find_inspectEnvelope
      (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact (VSCore3.recordRawLaws "Envelope" (VSCore3.RecordLayout.cons "parcel" (VSCore3.RecordLayout.cons "active" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Parcel" (VSCore3.RecordLayout.cons "shade" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws))))
      adapter_1_raw

abbrev entry_keepParcel : VSCore3.CompiledFunction :=
  { id := "keepParcel", params := [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))], result := (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))),
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "keepParcel").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_keepParcel : VSCore3.findEntry checkedProgram "keepParcel" = some entry_keepParcel := by with_unfolding_all rfl
def source_fn_keepParcel (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @VeriSlopAST.Parcel) : (@List.{0} @VeriSlopAST.Envelope) := by
  with_unfolding_all exact adapter_5.inv (entry_keepParcel.run (adapter_5.to x__0, (adapter_2.to x__1, ())))
def Refines_keepParcel : Prop := (∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @VeriSlopAST.Parcel), (@Eq.{1} (@List.{0} @VeriSlopAST.Envelope) (@VeriSlopBridgeGoal.source_fn_keepParcel x__0 x__1) (@VeriSlopAST.keepParcel x__0 x__1))))
def RawEval_keepParcel : Prop := ∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @VeriSlopAST.Parcel),
  VSCore3.evalEntry profile rawProgram "keepParcel" [adapter_5.encode x__0, adapter_2.encode x__1] =
    .ok (adapter_5.encode (source_fn_keepParcel x__0 x__1))
theorem raw_eval_keepParcel : RawEval_keepParcel := by
  with_unfolding_all
    intro x__0 x__1
    have hd : VSCore3.decodeEnv entry_keepParcel.params [adapter_5.encode x__0, adapter_2.encode x__1] = some (adapter_5.to x__0, (adapter_2.to x__1, ())) := by
      change VSCore3.decodeEnv [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))] [adapter_5.encode x__0, adapter_2.encode x__1] = some (adapter_5.to x__0, (adapter_2.to x__1, ()))
      simp only [VSCore3.decodeEnv, adapter_5_decode_encode, adapter_2_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "keepParcel" [adapter_5.encode x__0, adapter_2.encode x__1] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_keepParcel, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_keepParcel, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) (entry_keepParcel.run (adapter_5.to x__0, (adapter_2.to x__1, ())))) =
      Except.ok (VSCore3.encode (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) (adapter_5.to (adapter_5.inv (entry_keepParcel.run (adapter_5.to x__0, (adapter_2.to x__1, ()))))))
    rw [adapter_5.to_from]
def InputsCover_keepParcel : Prop := ∀ args, VSCore3.ArgsTyped entry_keepParcel args → ∃ (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @VeriSlopAST.Parcel), args = [adapter_5.encode x__0, adapter_2.encode x__1]
theorem inputs_cover_keepParcel : InputsCover_keepParcel := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl
    · exact (VSCore3.listRawLaws (VSCore3.recordRawLaws "Envelope" (VSCore3.RecordLayout.cons "parcel" (VSCore3.RecordLayout.cons "active" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Parcel" (VSCore3.RecordLayout.cons "shade" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws))))
    · exact (VSCore3.recordRawLaws "Parcel" (VSCore3.RecordLayout.cons "shade" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws)))) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    cases env
    refine ⟨adapter_5.inv v__0, adapter_2.inv v__1, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_5.to_from, adapter_2.to_from] using he.symm

abbrev entry_sameShade : VSCore3.CompiledFunction :=
  { id := "sameShade", params := [(.enum "Shade" ["light", "dark", "neutral"]), (.enum "Shade" ["light", "dark", "neutral"])], result := .bool,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "sameShade").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_sameShade : VSCore3.findEntry checkedProgram "sameShade" = some entry_sameShade := by with_unfolding_all rfl
def source_fn_sameShade (x__0 : @VeriSlopAST.Shade) (x__1 : @VeriSlopAST.Shade) : @Bool := by
  with_unfolding_all exact adapter_3.inv (entry_sameShade.run (adapter_0.to x__0, (adapter_0.to x__1, ())))
def Refines_sameShade : Prop := (∀ (x__0 : @VeriSlopAST.Shade), (∀ (x__1 : @VeriSlopAST.Shade), (@Eq.{1} @Bool (@VeriSlopBridgeGoal.source_fn_sameShade x__0 x__1) (@VeriSlopAST.sameShade x__0 x__1))))
def RawEval_sameShade : Prop := ∀ (x__0 : @VeriSlopAST.Shade) (x__1 : @VeriSlopAST.Shade),
  VSCore3.evalEntry profile rawProgram "sameShade" [adapter_0.encode x__0, adapter_0.encode x__1] =
    .ok (adapter_3.encode (source_fn_sameShade x__0 x__1))
theorem raw_eval_sameShade : RawEval_sameShade := by
  with_unfolding_all
    intro x__0 x__1
    have hd : VSCore3.decodeEnv entry_sameShade.params [adapter_0.encode x__0, adapter_0.encode x__1] = some (adapter_0.to x__0, (adapter_0.to x__1, ())) := by
      change VSCore3.decodeEnv [(.enum "Shade" ["light", "dark", "neutral"]), (.enum "Shade" ["light", "dark", "neutral"])] [adapter_0.encode x__0, adapter_0.encode x__1] = some (adapter_0.to x__0, (adapter_0.to x__1, ()))
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, adapter_0_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "sameShade" [adapter_0.encode x__0, adapter_0.encode x__1] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_sameShade, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_sameShade, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .bool (entry_sameShade.run (adapter_0.to x__0, (adapter_0.to x__1, ())))) =
      Except.ok (VSCore3.encode .bool (adapter_3.to (adapter_3.inv (entry_sameShade.run (adapter_0.to x__0, (adapter_0.to x__1, ()))))))
    rw [adapter_3.to_from]
def InputsCover_sameShade : Prop := ∀ args, VSCore3.ArgsTyped entry_sameShade args → ∃ (x__0 : @VeriSlopAST.Shade) (x__1 : @VeriSlopAST.Shade), args = [adapter_0.encode x__0, adapter_0.encode x__1]
theorem inputs_cover_sameShade : InputsCover_sameShade := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [(.enum "Shade" ["light", "dark", "neutral"]), (.enum "Shade" ["light", "dark", "neutral"])] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [(.enum "Shade" ["light", "dark", "neutral"]), (.enum "Shade" ["light", "dark", "neutral"])] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl
    · exact (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"])
    · exact (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"])) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    cases env
    refine ⟨adapter_0.inv v__0, adapter_0.inv v__1, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_0.to_from, adapter_0.to_from] using he.symm

abbrev entry_shadeTotal : VSCore3.CompiledFunction :=
  { id := "shadeTotal", params := [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), .nat, (.enum "Shade" ["light", "dark", "neutral"])], result := .nat,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "shadeTotal").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_shadeTotal : VSCore3.findEntry checkedProgram "shadeTotal" = some entry_shadeTotal := by with_unfolding_all rfl
def source_fn_shadeTotal (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) (x__2 : @VeriSlopAST.Shade) : @Nat := by
  with_unfolding_all exact adapter_1.inv (entry_shadeTotal.run (adapter_5.to x__0, (adapter_1.to x__1, (adapter_0.to x__2, ()))))
def Refines_shadeTotal : Prop := (∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @Nat), (∀ (x__2 : @VeriSlopAST.Shade), (@Eq.{1} @Nat (@VeriSlopBridgeGoal.source_fn_shadeTotal x__0 x__1 x__2) (@VeriSlopAST.shadeTotal x__0 x__1 x__2)))))
def RawEval_shadeTotal : Prop := ∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) (x__2 : @VeriSlopAST.Shade),
  VSCore3.evalEntry profile rawProgram "shadeTotal" [adapter_5.encode x__0, adapter_1.encode x__1, adapter_0.encode x__2] =
    .ok (adapter_1.encode (source_fn_shadeTotal x__0 x__1 x__2))
theorem raw_eval_shadeTotal : RawEval_shadeTotal := by
  with_unfolding_all
    intro x__0 x__1 x__2
    have hd : VSCore3.decodeEnv entry_shadeTotal.params [adapter_5.encode x__0, adapter_1.encode x__1, adapter_0.encode x__2] = some (adapter_5.to x__0, (adapter_1.to x__1, (adapter_0.to x__2, ()))) := by
      change VSCore3.decodeEnv [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), .nat, (.enum "Shade" ["light", "dark", "neutral"])] [adapter_5.encode x__0, adapter_1.encode x__1, adapter_0.encode x__2] = some (adapter_5.to x__0, (adapter_1.to x__1, (adapter_0.to x__2, ())))
      simp only [VSCore3.decodeEnv, adapter_5_decode_encode, adapter_1_decode_encode, adapter_0_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "shadeTotal" [adapter_5.encode x__0, adapter_1.encode x__1, adapter_0.encode x__2] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_shadeTotal, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_shadeTotal, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .nat (entry_shadeTotal.run (adapter_5.to x__0, (adapter_1.to x__1, (adapter_0.to x__2, ()))))) =
      Except.ok (VSCore3.encode .nat (adapter_1.to (adapter_1.inv (entry_shadeTotal.run (adapter_5.to x__0, (adapter_1.to x__1, (adapter_0.to x__2, ())))))))
    rw [adapter_1.to_from]
def InputsCover_shadeTotal : Prop := ∀ args, VSCore3.ArgsTyped entry_shadeTotal args → ∃ (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) (x__2 : @VeriSlopAST.Shade), args = [adapter_5.encode x__0, adapter_1.encode x__1, adapter_0.encode x__2]
theorem inputs_cover_shadeTotal : InputsCover_shadeTotal := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), .nat, (.enum "Shade" ["light", "dark", "neutral"])] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), .nat, (.enum "Shade" ["light", "dark", "neutral"])] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl | rfl
    · exact (VSCore3.listRawLaws (VSCore3.recordRawLaws "Envelope" (VSCore3.RecordLayout.cons "parcel" (VSCore3.RecordLayout.cons "active" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Parcel" (VSCore3.RecordLayout.cons "shade" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws))))
    · exact VSCore3.natRawLaws
    · exact (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"])) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    rcases env with ⟨v__2, env⟩
    cases env
    refine ⟨adapter_5.inv v__0, adapter_1.inv v__1, adapter_0.inv v__2, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_5.to_from, adapter_1.to_from, adapter_0.to_from] using he.symm

abbrev entry_shiftEnvelopes : VSCore3.CompiledFunction :=
  { id := "shiftEnvelopes", params := [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), .nat], result := (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))),
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "shiftEnvelopes").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_shiftEnvelopes : VSCore3.findEntry checkedProgram "shiftEnvelopes" = some entry_shiftEnvelopes := by with_unfolding_all rfl
def source_fn_shiftEnvelopes (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) : (@List.{0} @VeriSlopAST.Envelope) := by
  with_unfolding_all exact adapter_5.inv (entry_shiftEnvelopes.run (adapter_5.to x__0, (adapter_1.to x__1, ())))
def Refines_shiftEnvelopes : Prop := (∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @Nat), (@Eq.{1} (@List.{0} @VeriSlopAST.Envelope) (@VeriSlopBridgeGoal.source_fn_shiftEnvelopes x__0 x__1) (@VeriSlopAST.shiftEnvelopes x__0 x__1))))
def RawEval_shiftEnvelopes : Prop := ∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat),
  VSCore3.evalEntry profile rawProgram "shiftEnvelopes" [adapter_5.encode x__0, adapter_1.encode x__1] =
    .ok (adapter_5.encode (source_fn_shiftEnvelopes x__0 x__1))
theorem raw_eval_shiftEnvelopes : RawEval_shiftEnvelopes := by
  with_unfolding_all
    intro x__0 x__1
    have hd : VSCore3.decodeEnv entry_shiftEnvelopes.params [adapter_5.encode x__0, adapter_1.encode x__1] = some (adapter_5.to x__0, (adapter_1.to x__1, ())) := by
      change VSCore3.decodeEnv [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), .nat] [adapter_5.encode x__0, adapter_1.encode x__1] = some (adapter_5.to x__0, (adapter_1.to x__1, ()))
      simp only [VSCore3.decodeEnv, adapter_5_decode_encode, adapter_1_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "shiftEnvelopes" [adapter_5.encode x__0, adapter_1.encode x__1] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_shiftEnvelopes, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_shiftEnvelopes, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) (entry_shiftEnvelopes.run (adapter_5.to x__0, (adapter_1.to x__1, ())))) =
      Except.ok (VSCore3.encode (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) (adapter_5.to (adapter_5.inv (entry_shiftEnvelopes.run (adapter_5.to x__0, (adapter_1.to x__1, ()))))))
    rw [adapter_5.to_from]
def InputsCover_shiftEnvelopes : Prop := ∀ args, VSCore3.ArgsTyped entry_shiftEnvelopes args → ∃ (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat), args = [adapter_5.encode x__0, adapter_1.encode x__1]
theorem inputs_cover_shiftEnvelopes : InputsCover_shiftEnvelopes := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), .nat] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), .nat] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl
    · exact (VSCore3.listRawLaws (VSCore3.recordRawLaws "Envelope" (VSCore3.RecordLayout.cons "parcel" (VSCore3.RecordLayout.cons "active" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Parcel" (VSCore3.RecordLayout.cons "shade" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws))))
    · exact VSCore3.natRawLaws) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    cases env
    refine ⟨adapter_5.inv v__0, adapter_1.inv v__1, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_5.to_from, adapter_1.to_from] using he.symm

def sourceFacts_shiftEnvelopes : VeriSlop.Source.ModuleFacts :=
  let m := VSCore3.exactSourceFacts profile rawProgram "shiftEnvelopes"
  { entries := m.entries.map (fun e => ⟨e.file, e.id, e.arity⟩),
    uniqueEntries := m.uniqueEntries, typedTotal := m.typedTotal, deterministic := m.deterministic,
    inputPreserved := m.inputPreserved, noExternalIO := m.noExternalIO,
    noFloatingPoint := m.noFloatingPoint, pureData := m.pureData,
    restrictedRuntimeOnly := m.restrictedRuntimeOnly }
def SourceAdequate_shiftEnvelopes : Prop :=
  VSCore3.SourceFactsAdequate profile rawProgram "shiftEnvelopes" checkedProgram entry_shiftEnvelopes
theorem source_adequate_shiftEnvelopes : SourceAdequate_shiftEnvelopes := by
  with_unfolding_all
    exact VSCore3.exactSourceFacts_adequate compiled_ok find_shiftEnvelopes
      (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl
    · exact (VSCore3.listRawLaws (VSCore3.recordRawLaws "Envelope" (VSCore3.RecordLayout.cons "parcel" (VSCore3.RecordLayout.cons "active" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Parcel" (VSCore3.RecordLayout.cons "shade" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Shade" ["light", "dark", "neutral"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws))))
    · exact VSCore3.natRawLaws)
      adapter_5_raw

/-- Accepted obligation G-equality, theorem VeriSlopAST.law_equality, hash sha256:8f1171af32aec842fa8c72938181e2ae0b4e59e7af7bf46d3090a5b1c9fef959. -/
def «Transfer_G-equality» : Prop := (∀ (x__0 : @VeriSlopAST.Shade), (∀ (x__1 : @VeriSlopAST.Shade), (@Eq.{1} @Bool (@VeriSlopBridgeGoal.source_fn_sameShade x__0 x__1) (@Decidable.decide (@Eq.{1} @VeriSlopAST.Shade x__0 x__1) (@VeriSlopAST.instDecidableEqShade x__0 x__1)))))
theorem «transfer_G-equality» (h_sameShade : Refines_sameShade) : «Transfer_G-equality» := by
  have eq_sameShade : source_fn_sameShade = @VeriSlopAST.sameShade := by
    apply funext; intro x__0; apply funext; intro x__1
    exact h_sameShade x__0 x__1
  have htransfer : ((∀ (x__0 : @VeriSlopAST.Shade), (∀ (x__1 : @VeriSlopAST.Shade), (@Eq.{1} @Bool (@VeriSlopBridgeGoal.source_fn_sameShade x__0 x__1) (@Decidable.decide (@Eq.{1} @VeriSlopAST.Shade x__0 x__1) (@VeriSlopAST.instDecidableEqShade x__0 x__1)))))) = ((∀ (x__0 : @VeriSlopAST.Shade), (∀ (x__1 : @VeriSlopAST.Shade), (@Eq.{1} @Bool (@VeriSlopAST.sameShade x__0 x__1) (@Decidable.decide (@Eq.{1} @VeriSlopAST.Shade x__0 x__1) (@VeriSlopAST.instDecidableEqShade x__0 x__1)))))) := by
    rw [eq_sameShade]
  have hvalue : ((∀ (x__0 : @VeriSlopAST.Shade), (∀ (x__1 : @VeriSlopAST.Shade), (@Eq.{1} @Bool (@VeriSlopBridgeGoal.source_fn_sameShade x__0 x__1) (@Decidable.decide (@Eq.{1} @VeriSlopAST.Shade x__0 x__1) (@VeriSlopAST.instDecidableEqShade x__0 x__1)))))) := htransfer.symm ▸ (@VeriSlopAST.law_equality)
  exact hvalue

/-- Accepted obligation G-map, theorem VeriSlopAST.law_shift, hash sha256:01ae54d10758bb288fe7e09e5cfbc51e558009e6c58a744a9dc5b02a008e0fc3. -/
def «Transfer_G-map» : Prop := (@And (∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @Nat), (@Eq.{1} (@List.{0} @VeriSlopAST.Envelope) (@VeriSlopBridgeGoal.source_fn_shiftEnvelopes x__0 x__1) (@List.map.{0, 0} @VeriSlopAST.Envelope @VeriSlopAST.Envelope (fun (x__2 : @VeriSlopAST.Envelope) => (@VeriSlopAST.Envelope.mk (@VeriSlopAST.Parcel.mk (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__2)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__2)) x__1)) (@VeriSlopAST.Envelope.active x__2))) x__0)))) (@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @Nat), (@List.{0} @VeriSlopAST.Envelope))) @VeriSlopAST.MapDelivery) @VeriSlopBridgeGoal.sourceFacts_shiftEnvelopes))
theorem «transfer_G-map» (h_shiftEnvelopes : Refines_shiftEnvelopes) : «Transfer_G-map» := by
  have haccepted := @VeriSlopAST.law_shift
  have eq_shiftEnvelopes : source_fn_shiftEnvelopes = @VeriSlopAST.shiftEnvelopes := by
    apply funext; intro x__0; apply funext; intro x__1
    exact h_shiftEnvelopes x__0 x__1
  have htransfer : ((∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @Nat), (@Eq.{1} (@List.{0} @VeriSlopAST.Envelope) (@VeriSlopBridgeGoal.source_fn_shiftEnvelopes x__0 x__1) (@List.map.{0, 0} @VeriSlopAST.Envelope @VeriSlopAST.Envelope (fun (x__2 : @VeriSlopAST.Envelope) => (@VeriSlopAST.Envelope.mk (@VeriSlopAST.Parcel.mk (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__2)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__2)) x__1)) (@VeriSlopAST.Envelope.active x__2))) x__0))))) = ((∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @Nat), (@Eq.{1} (@List.{0} @VeriSlopAST.Envelope) (@VeriSlopAST.shiftEnvelopes x__0 x__1) (@List.map.{0, 0} @VeriSlopAST.Envelope @VeriSlopAST.Envelope (fun (x__2 : @VeriSlopAST.Envelope) => (@VeriSlopAST.Envelope.mk (@VeriSlopAST.Parcel.mk (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__2)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__2)) x__1)) (@VeriSlopAST.Envelope.active x__2))) x__0))))) := by
    rw [eq_shiftEnvelopes]
  have hvalue : ((∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @Nat), (@Eq.{1} (@List.{0} @VeriSlopAST.Envelope) (@VeriSlopBridgeGoal.source_fn_shiftEnvelopes x__0 x__1) (@List.map.{0, 0} @VeriSlopAST.Envelope @VeriSlopAST.Envelope (fun (x__2 : @VeriSlopAST.Envelope) => (@VeriSlopAST.Envelope.mk (@VeriSlopAST.Parcel.mk (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__2)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__2)) x__1)) (@VeriSlopAST.Envelope.active x__2))) x__0))))) := htransfer.symm ▸ (haccepted.1)
  have hsource_0 : ((@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @Nat), (@List.{0} @VeriSlopAST.Envelope))) @VeriSlopAST.MapDelivery) @VeriSlopBridgeGoal.sourceFacts_shiftEnvelopes)) := by
    apply (haccepted.2).1 sourceFacts_shiftEnvelopes
    with_unfolding_all rfl
  exact ⟨hvalue, hsource_0⟩

/-- Accepted obligation G.filter, theorem VeriSlopAST.law_filter, hash sha256:b59b328b6d724564c6408801b458bf3aa131edd3c9d139f9087f41a1b27e30c5. -/
def «Transfer_G.filter» : Prop := (∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @VeriSlopAST.Parcel), (@Eq.{1} (@List.{0} @VeriSlopAST.Envelope) (@VeriSlopBridgeGoal.source_fn_keepParcel x__0 x__1) (@List.filter.{0} @VeriSlopAST.Envelope (fun (x__2 : @VeriSlopAST.Envelope) => (@Bool.and (@Decidable.decide (@Eq.{1} @VeriSlopAST.Shade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.shade x__1)) (@VeriSlopAST.instDecidableEqShade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.shade x__1))) (@Decidable.decide (@Eq.{1} @Nat (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.n x__1)) (@instDecidableEqNat (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.n x__1))))) x__0))))
theorem «transfer_G.filter» (h_keepParcel : Refines_keepParcel) : «Transfer_G.filter» := by
  have eq_keepParcel : source_fn_keepParcel = @VeriSlopAST.keepParcel := by
    apply funext; intro x__0; apply funext; intro x__1
    exact h_keepParcel x__0 x__1
  have htransfer : ((∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @VeriSlopAST.Parcel), (@Eq.{1} (@List.{0} @VeriSlopAST.Envelope) (@VeriSlopBridgeGoal.source_fn_keepParcel x__0 x__1) (@List.filter.{0} @VeriSlopAST.Envelope (fun (x__2 : @VeriSlopAST.Envelope) => (@Bool.and (@Decidable.decide (@Eq.{1} @VeriSlopAST.Shade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.shade x__1)) (@VeriSlopAST.instDecidableEqShade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.shade x__1))) (@Decidable.decide (@Eq.{1} @Nat (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.n x__1)) (@instDecidableEqNat (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.n x__1))))) x__0))))) = ((∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @VeriSlopAST.Parcel), (@Eq.{1} (@List.{0} @VeriSlopAST.Envelope) (@VeriSlopAST.keepParcel x__0 x__1) (@List.filter.{0} @VeriSlopAST.Envelope (fun (x__2 : @VeriSlopAST.Envelope) => (@Bool.and (@Decidable.decide (@Eq.{1} @VeriSlopAST.Shade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.shade x__1)) (@VeriSlopAST.instDecidableEqShade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.shade x__1))) (@Decidable.decide (@Eq.{1} @Nat (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.n x__1)) (@instDecidableEqNat (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.n x__1))))) x__0))))) := by
    rw [eq_keepParcel]
  have hvalue : ((∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @VeriSlopAST.Parcel), (@Eq.{1} (@List.{0} @VeriSlopAST.Envelope) (@VeriSlopBridgeGoal.source_fn_keepParcel x__0 x__1) (@List.filter.{0} @VeriSlopAST.Envelope (fun (x__2 : @VeriSlopAST.Envelope) => (@Bool.and (@Decidable.decide (@Eq.{1} @VeriSlopAST.Shade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.shade x__1)) (@VeriSlopAST.instDecidableEqShade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.shade x__1))) (@Decidable.decide (@Eq.{1} @Nat (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.n x__1)) (@instDecidableEqNat (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__2)) (@VeriSlopAST.Parcel.n x__1))))) x__0))))) := htransfer.symm ▸ (@VeriSlopAST.law_filter)
  exact hvalue

/-- Accepted obligation G:fold, theorem VeriSlopAST.law_fold, hash sha256:1451b0eb30840d4e667d46110ea44b4f56c43c4eb4552d80dc50e74b56c335f9. -/
def «Transfer_G:fold» : Prop := (∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @Nat), (∀ (x__2 : @VeriSlopAST.Shade), (@Eq.{1} @Nat (@VeriSlopBridgeGoal.source_fn_shadeTotal x__0 x__1 x__2) (@List.foldl.{0, 0} @Nat @VeriSlopAST.Envelope (fun (acc__3 : @Nat) => (fun (x__4 : @VeriSlopAST.Envelope) => (@cond.{1} @Nat (@Decidable.decide (@Eq.{1} @VeriSlopAST.Shade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__4)) x__2) (@VeriSlopAST.instDecidableEqShade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__4)) x__2)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) acc__3 (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__4))) acc__3))) x__1 x__0)))))
theorem «transfer_G:fold» (h_shadeTotal : Refines_shadeTotal) : «Transfer_G:fold» := by
  have eq_shadeTotal : source_fn_shadeTotal = @VeriSlopAST.shadeTotal := by
    apply funext; intro x__0; apply funext; intro x__1; apply funext; intro x__2
    exact h_shadeTotal x__0 x__1 x__2
  have htransfer : ((∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @Nat), (∀ (x__2 : @VeriSlopAST.Shade), (@Eq.{1} @Nat (@VeriSlopBridgeGoal.source_fn_shadeTotal x__0 x__1 x__2) (@List.foldl.{0, 0} @Nat @VeriSlopAST.Envelope (fun (acc__3 : @Nat) => (fun (x__4 : @VeriSlopAST.Envelope) => (@cond.{1} @Nat (@Decidable.decide (@Eq.{1} @VeriSlopAST.Shade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__4)) x__2) (@VeriSlopAST.instDecidableEqShade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__4)) x__2)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) acc__3 (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__4))) acc__3))) x__1 x__0)))))) = ((∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @Nat), (∀ (x__2 : @VeriSlopAST.Shade), (@Eq.{1} @Nat (@VeriSlopAST.shadeTotal x__0 x__1 x__2) (@List.foldl.{0, 0} @Nat @VeriSlopAST.Envelope (fun (acc__3 : @Nat) => (fun (x__4 : @VeriSlopAST.Envelope) => (@cond.{1} @Nat (@Decidable.decide (@Eq.{1} @VeriSlopAST.Shade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__4)) x__2) (@VeriSlopAST.instDecidableEqShade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__4)) x__2)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) acc__3 (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__4))) acc__3))) x__1 x__0)))))) := by
    rw [eq_shadeTotal]
  have hvalue : ((∀ (x__0 : (@List.{0} @VeriSlopAST.Envelope)), (∀ (x__1 : @Nat), (∀ (x__2 : @VeriSlopAST.Shade), (@Eq.{1} @Nat (@VeriSlopBridgeGoal.source_fn_shadeTotal x__0 x__1 x__2) (@List.foldl.{0, 0} @Nat @VeriSlopAST.Envelope (fun (acc__3 : @Nat) => (fun (x__4 : @VeriSlopAST.Envelope) => (@cond.{1} @Nat (@Decidable.decide (@Eq.{1} @VeriSlopAST.Shade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__4)) x__2) (@VeriSlopAST.instDecidableEqShade (@VeriSlopAST.Parcel.shade (@VeriSlopAST.Envelope.parcel x__4)) x__2)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) acc__3 (@VeriSlopAST.Parcel.n (@VeriSlopAST.Envelope.parcel x__4))) acc__3))) x__1 x__0)))))) := htransfer.symm ▸ (@VeriSlopAST.law_fold)
  exact hvalue

/-- Accepted obligation S:delivery.only, theorem VeriSlopAST.source_delivery, hash sha256:3476a9afa134e67e131cd15957f3de7442ed43c547699b08b5037635dc4151fb. -/
def «Transfer_S:delivery.only» : Prop := (@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Envelope), @Nat) @VeriSlopAST.InspectDelivery) @VeriSlopBridgeGoal.sourceFacts_inspectEnvelope)
theorem «transfer_S:delivery.only»  : «Transfer_S:delivery.only» := by
  have haccepted := @VeriSlopAST.source_delivery
  have hsource_0 : ((@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Envelope), @Nat) @VeriSlopAST.InspectDelivery) @VeriSlopBridgeGoal.sourceFacts_inspectEnvelope)) := by
    apply (haccepted).1 sourceFacts_inspectEnvelope
    with_unfolding_all rfl
  exact hsource_0

def EdgeProp : Prop := (@And @VeriSlopBridgeGoal.SourceParses (@And @VeriSlopBridgeGoal.SourceChecks (@And @VeriSlopBridgeGoal.InputsCover_inspectEnvelope (@And @VeriSlopBridgeGoal.RawEval_inspectEnvelope (@And @VeriSlopBridgeGoal.SourceAdequate_inspectEnvelope (@And @VeriSlopBridgeGoal.InputsCover_keepParcel (@And @VeriSlopBridgeGoal.RawEval_keepParcel (@And @VeriSlopBridgeGoal.Refines_keepParcel (@And @VeriSlopBridgeGoal.InputsCover_sameShade (@And @VeriSlopBridgeGoal.RawEval_sameShade (@And @VeriSlopBridgeGoal.Refines_sameShade (@And @VeriSlopBridgeGoal.InputsCover_shadeTotal (@And @VeriSlopBridgeGoal.RawEval_shadeTotal (@And @VeriSlopBridgeGoal.Refines_shadeTotal (@And @VeriSlopBridgeGoal.InputsCover_shiftEnvelopes (@And @VeriSlopBridgeGoal.RawEval_shiftEnvelopes (@And @VeriSlopBridgeGoal.Refines_shiftEnvelopes (@And @VeriSlopBridgeGoal.SourceAdequate_shiftEnvelopes (@And @VeriSlopBridgeGoal.«Transfer_G-equality» (@And @VeriSlopBridgeGoal.«Transfer_G-map» (@And @VeriSlopBridgeGoal.«Transfer_G.filter» (@And @VeriSlopBridgeGoal.«Transfer_G:fold» @VeriSlopBridgeGoal.«Transfer_S:delivery.only»))))))))))))))))))))))
theorem edge_of_refines (h_keepParcel : Refines_keepParcel) (h_sameShade : Refines_sameShade) (h_shadeTotal : Refines_shadeTotal) (h_shiftEnvelopes : Refines_shiftEnvelopes) : EdgeProp :=
  ⟨source_parses, source_checks, inputs_cover_inspectEnvelope, raw_eval_inspectEnvelope, source_adequate_inspectEnvelope, inputs_cover_keepParcel, raw_eval_keepParcel, h_keepParcel, inputs_cover_sameShade, raw_eval_sameShade, h_sameShade, inputs_cover_shadeTotal, raw_eval_shadeTotal, h_shadeTotal, inputs_cover_shiftEnvelopes, raw_eval_shiftEnvelopes, h_shiftEnvelopes, source_adequate_shiftEnvelopes, «transfer_G-equality» h_sameShade, «transfer_G-map» h_shiftEnvelopes, «transfer_G.filter» h_keepParcel, «transfer_G:fold» h_shadeTotal, «transfer_S:delivery.only» ⟩

end VeriSlopBridgeGoal

namespace VeriSlopReadableSource
abbrev helper_0_params : List VSCore3.Shape := [.nat, (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))]
abbrev helper_0_result : VSCore3.Shape := (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))
def helper_0_body (env : VSCore3.Env helper_0_params.reverse) : VSCore3.Denote helper_0_result := by
  with_unfolding_all exact ((((env).1).1, (((((env).1).2.1) + ((env).2.1)), ())) : VSCore3.Denote (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))))
def helper_0_run (env : VSCore3.Env helper_0_params) : VSCore3.Denote helper_0_result :=
  helper_0_body (VSCore3.envReverse helper_0_params env)
def helper_0_named (p__0 : VSCore3.Denote .nat) (p__1 : VSCore3.Denote (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))) : VSCore3.Denote helper_0_result :=
  helper_0_run (p__0, (p__1, ()))
abbrev helper_1_params : List VSCore3.Shape := [.nat, (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))]
abbrev helper_1_result : VSCore3.Shape := (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))
def helper_1_body (env : VSCore3.Env helper_1_params.reverse) : VSCore3.Denote helper_1_result := by
  with_unfolding_all exact (((helper_0_named ((env).2.1) (((env).1).1)), (((env).1).2.1, ())) : VSCore3.Denote (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))))
def helper_1_run (env : VSCore3.Env helper_1_params) : VSCore3.Denote helper_1_result :=
  helper_1_body (VSCore3.envReverse helper_1_params env)
def helper_1_named (p__0 : VSCore3.Denote .nat) (p__1 : VSCore3.Denote (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) : VSCore3.Denote helper_1_result :=
  helper_1_run (p__0, (p__1, ()))
abbrev helper_2_params : List VSCore3.Shape := [(.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))), (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))]
abbrev helper_2_result : VSCore3.Shape := .bool
def helper_2_body (env : VSCore3.Env helper_2_params.reverse) : VSCore3.Denote helper_2_result := by
  with_unfolding_all exact (letI := VSCore3.denoteDecidableEq (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))); decide ((((env).1).1) = ((env).2.1)))
def helper_2_run (env : VSCore3.Env helper_2_params) : VSCore3.Denote helper_2_result :=
  helper_2_body (VSCore3.envReverse helper_2_params env)
def helper_2_named (p__0 : VSCore3.Denote (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))) (p__1 : VSCore3.Denote (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) : VSCore3.Denote helper_2_result :=
  helper_2_run (p__0, (p__1, ()))
abbrev helper_3_params : List VSCore3.Shape := [(.enum "Shade" ["light", "dark", "neutral"]), .nat, (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))]
abbrev helper_3_result : VSCore3.Shape := .nat
def helper_3_body (env : VSCore3.Env helper_3_params.reverse) : VSCore3.Denote helper_3_result := by
  with_unfolding_all exact (if ((letI := VSCore3.denoteDecidableEq (.enum "Shade" ["light", "dark", "neutral"]); decide (((((env).1).1).1) = ((env).2.2.1)))) then ((((env).2.1) + ((((env).1).1).2.1))) else ((env).2.1))
def helper_3_run (env : VSCore3.Env helper_3_params) : VSCore3.Denote helper_3_result :=
  helper_3_body (VSCore3.envReverse helper_3_params env)
def helper_3_named (p__0 : VSCore3.Denote (.enum "Shade" ["light", "dark", "neutral"])) (p__1 : VSCore3.Denote .nat) (p__2 : VSCore3.Denote (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) : VSCore3.Denote helper_3_result :=
  helper_3_run (p__0, (p__1, (p__2, ())))
abbrev entry_0_params : List VSCore3.Shape := [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), .nat]
abbrev entry_0_result : VSCore3.Shape := (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))))
def entry_0_body (env : VSCore3.Env entry_0_params.reverse) : VSCore3.Denote entry_0_result := by
  with_unfolding_all exact (List.map (fun v__1 => ((helper_1_named ((env).1) (v__1)))) ((env).2.1))
def entry_0_run (env : VSCore3.Env entry_0_params) : VSCore3.Denote entry_0_result :=
  entry_0_body (VSCore3.envReverse entry_0_params env)
def entry_0_named (p__0 : VSCore3.Denote (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))))) (p__1 : VSCore3.Denote .nat) : VSCore3.Denote entry_0_result :=
  entry_0_run (p__0, (p__1, ()))
abbrev entry_1_params : List VSCore3.Shape := [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))]
abbrev entry_1_result : VSCore3.Shape := (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))))
def entry_1_body (env : VSCore3.Env entry_1_params.reverse) : VSCore3.Denote entry_1_result := by
  with_unfolding_all exact (List.filter (fun v__1 => ((helper_2_named ((env).1) (v__1)))) ((env).2.1))
def entry_1_run (env : VSCore3.Env entry_1_params) : VSCore3.Denote entry_1_result :=
  entry_1_body (VSCore3.envReverse entry_1_params env)
def entry_1_named (p__0 : VSCore3.Denote (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))))) (p__1 : VSCore3.Denote (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))) : VSCore3.Denote entry_1_result :=
  entry_1_run (p__0, (p__1, ()))
abbrev entry_2_params : List VSCore3.Shape := [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), .nat, (.enum "Shade" ["light", "dark", "neutral"])]
abbrev entry_2_result : VSCore3.Shape := .nat
def entry_2_body (env : VSCore3.Env entry_2_params.reverse) : VSCore3.Denote entry_2_result := by
  with_unfolding_all exact (List.foldl (fun v__1 v__2 => ((helper_3_named ((env).1) (v__1) (v__2)))) ((env).2.1) ((env).2.2.1))
def entry_2_run (env : VSCore3.Env entry_2_params) : VSCore3.Denote entry_2_result :=
  entry_2_body (VSCore3.envReverse entry_2_params env)
def entry_2_named (p__0 : VSCore3.Denote (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))))) (p__1 : VSCore3.Denote .nat) (p__2 : VSCore3.Denote (.enum "Shade" ["light", "dark", "neutral"])) : VSCore3.Denote entry_2_result :=
  entry_2_run (p__0, (p__1, (p__2, ())))
abbrev entry_3_params : List VSCore3.Shape := [(.enum "Shade" ["light", "dark", "neutral"]), (.enum "Shade" ["light", "dark", "neutral"])]
abbrev entry_3_result : VSCore3.Shape := .bool
def entry_3_body (env : VSCore3.Env entry_3_params.reverse) : VSCore3.Denote entry_3_result := by
  with_unfolding_all exact (letI := VSCore3.denoteDecidableEq (.enum "Shade" ["light", "dark", "neutral"]); decide (((env).2.1) = ((env).1)))
def entry_3_run (env : VSCore3.Env entry_3_params) : VSCore3.Denote entry_3_result :=
  entry_3_body (VSCore3.envReverse entry_3_params env)
def entry_3_named (p__0 : VSCore3.Denote (.enum "Shade" ["light", "dark", "neutral"])) (p__1 : VSCore3.Denote (.enum "Shade" ["light", "dark", "neutral"])) : VSCore3.Denote entry_3_result :=
  entry_3_run (p__0, (p__1, ()))
abbrev entry_4_params : List VSCore3.Shape := [(.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))]
abbrev entry_4_result : VSCore3.Shape := .nat
def entry_4_body (env : VSCore3.Env entry_4_params.reverse) : VSCore3.Denote entry_4_result := by
  with_unfolding_all exact (0 : Nat)
def entry_4_run (env : VSCore3.Env entry_4_params) : VSCore3.Denote entry_4_result :=
  entry_4_body (VSCore3.envReverse entry_4_params env)
def entry_4_named (p__0 : VSCore3.Denote (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) : VSCore3.Denote entry_4_result :=
  entry_4_run (p__0, ())
end VeriSlopReadableSource

namespace VeriSlopBridgeGoal.Readable
abbrev helper_0_compiled : VSCore3.CompiledFunction :=
  { id := "shiftParcel", params := VeriSlopReadableSource.helper_0_params, result := VeriSlopReadableSource.helper_0_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "shiftParcel")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_0 : (checkedProgram.helpers.find? (fun h => h.id == "shiftParcel")) = some helper_0_compiled := by with_unfolding_all rfl
theorem signature_helper_0 : helper_0_compiled.params = VeriSlopReadableSource.helper_0_params ∧ helper_0_compiled.result = VeriSlopReadableSource.helper_0_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_0 : Prop := VSCore3.ReadableRunEquals helper_0_compiled VeriSlopReadableSource.helper_0_params VeriSlopReadableSource.helper_0_result VeriSlopReadableSource.helper_0_run
set_option smartUnfolding false in
theorem runEquals_helper_0 : RunEquals_helper_0 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_1_compiled : VSCore3.CompiledFunction :=
  { id := "shiftEnvelope", params := VeriSlopReadableSource.helper_1_params, result := VeriSlopReadableSource.helper_1_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "shiftEnvelope")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_1 : (checkedProgram.helpers.find? (fun h => h.id == "shiftEnvelope")) = some helper_1_compiled := by with_unfolding_all rfl
theorem signature_helper_1 : helper_1_compiled.params = VeriSlopReadableSource.helper_1_params ∧ helper_1_compiled.result = VeriSlopReadableSource.helper_1_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_1 : Prop := VSCore3.ReadableRunEquals helper_1_compiled VeriSlopReadableSource.helper_1_params VeriSlopReadableSource.helper_1_result VeriSlopReadableSource.helper_1_run
set_option smartUnfolding false in
theorem runEquals_helper_1 : RunEquals_helper_1 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_2_compiled : VSCore3.CompiledFunction :=
  { id := "keepEnvelope", params := VeriSlopReadableSource.helper_2_params, result := VeriSlopReadableSource.helper_2_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "keepEnvelope")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_2 : (checkedProgram.helpers.find? (fun h => h.id == "keepEnvelope")) = some helper_2_compiled := by with_unfolding_all rfl
theorem signature_helper_2 : helper_2_compiled.params = VeriSlopReadableSource.helper_2_params ∧ helper_2_compiled.result = VeriSlopReadableSource.helper_2_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_2 : Prop := VSCore3.ReadableRunEquals helper_2_compiled VeriSlopReadableSource.helper_2_params VeriSlopReadableSource.helper_2_result VeriSlopReadableSource.helper_2_run
set_option smartUnfolding false in
theorem runEquals_helper_2 : RunEquals_helper_2 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_3_compiled : VSCore3.CompiledFunction :=
  { id := "totalStep", params := VeriSlopReadableSource.helper_3_params, result := VeriSlopReadableSource.helper_3_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "totalStep")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_3 : (checkedProgram.helpers.find? (fun h => h.id == "totalStep")) = some helper_3_compiled := by with_unfolding_all rfl
theorem signature_helper_3 : helper_3_compiled.params = VeriSlopReadableSource.helper_3_params ∧ helper_3_compiled.result = VeriSlopReadableSource.helper_3_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_3 : Prop := VSCore3.ReadableRunEquals helper_3_compiled VeriSlopReadableSource.helper_3_params VeriSlopReadableSource.helper_3_result VeriSlopReadableSource.helper_3_run
set_option smartUnfolding false in
theorem runEquals_helper_3 : RunEquals_helper_3 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_0_compiled : VSCore3.CompiledFunction :=
  { id := "shiftEnvelopes", params := VeriSlopReadableSource.entry_0_params, result := VeriSlopReadableSource.entry_0_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "shiftEnvelopes").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_0 : (VSCore3.findEntry checkedProgram "shiftEnvelopes") = some entry_0_compiled := by with_unfolding_all rfl
theorem signature_entry_0 : entry_0_compiled.params = VeriSlopReadableSource.entry_0_params ∧ entry_0_compiled.result = VeriSlopReadableSource.entry_0_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_0 : Prop := VSCore3.ReadableRunEquals entry_0_compiled VeriSlopReadableSource.entry_0_params VeriSlopReadableSource.entry_0_result VeriSlopReadableSource.entry_0_run
set_option smartUnfolding false in
theorem runEquals_entry_0 : RunEquals_entry_0 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_1_compiled : VSCore3.CompiledFunction :=
  { id := "keepParcel", params := VeriSlopReadableSource.entry_1_params, result := VeriSlopReadableSource.entry_1_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "keepParcel").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_1 : (VSCore3.findEntry checkedProgram "keepParcel") = some entry_1_compiled := by with_unfolding_all rfl
theorem signature_entry_1 : entry_1_compiled.params = VeriSlopReadableSource.entry_1_params ∧ entry_1_compiled.result = VeriSlopReadableSource.entry_1_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_1 : Prop := VSCore3.ReadableRunEquals entry_1_compiled VeriSlopReadableSource.entry_1_params VeriSlopReadableSource.entry_1_result VeriSlopReadableSource.entry_1_run
set_option smartUnfolding false in
theorem runEquals_entry_1 : RunEquals_entry_1 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_2_compiled : VSCore3.CompiledFunction :=
  { id := "shadeTotal", params := VeriSlopReadableSource.entry_2_params, result := VeriSlopReadableSource.entry_2_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "shadeTotal").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_2 : (VSCore3.findEntry checkedProgram "shadeTotal") = some entry_2_compiled := by with_unfolding_all rfl
theorem signature_entry_2 : entry_2_compiled.params = VeriSlopReadableSource.entry_2_params ∧ entry_2_compiled.result = VeriSlopReadableSource.entry_2_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_2 : Prop := VSCore3.ReadableRunEquals entry_2_compiled VeriSlopReadableSource.entry_2_params VeriSlopReadableSource.entry_2_result VeriSlopReadableSource.entry_2_run
set_option smartUnfolding false in
theorem runEquals_entry_2 : RunEquals_entry_2 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_3_compiled : VSCore3.CompiledFunction :=
  { id := "sameShade", params := VeriSlopReadableSource.entry_3_params, result := VeriSlopReadableSource.entry_3_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "sameShade").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_3 : (VSCore3.findEntry checkedProgram "sameShade") = some entry_3_compiled := by with_unfolding_all rfl
theorem signature_entry_3 : entry_3_compiled.params = VeriSlopReadableSource.entry_3_params ∧ entry_3_compiled.result = VeriSlopReadableSource.entry_3_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_3 : Prop := VSCore3.ReadableRunEquals entry_3_compiled VeriSlopReadableSource.entry_3_params VeriSlopReadableSource.entry_3_result VeriSlopReadableSource.entry_3_run
set_option smartUnfolding false in
theorem runEquals_entry_3 : RunEquals_entry_3 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_4_compiled : VSCore3.CompiledFunction :=
  { id := "inspectEnvelope", params := VeriSlopReadableSource.entry_4_params, result := VeriSlopReadableSource.entry_4_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "inspectEnvelope").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_4 : (VSCore3.findEntry checkedProgram "inspectEnvelope") = some entry_4_compiled := by with_unfolding_all rfl
theorem signature_entry_4 : entry_4_compiled.params = VeriSlopReadableSource.entry_4_params ∧ entry_4_compiled.result = VeriSlopReadableSource.entry_4_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_4 : Prop := VSCore3.ReadableRunEquals entry_4_compiled VeriSlopReadableSource.entry_4_params VeriSlopReadableSource.entry_4_result VeriSlopReadableSource.entry_4_run
set_option smartUnfolding false in
theorem runEquals_entry_4 : RunEquals_entry_4 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
def readable_fn_inspectEnvelope (x__0 : @VeriSlopAST.Envelope) : @Nat := by
  with_unfolding_all exact adapter_1.inv (VeriSlopReadableSource.entry_4_run (adapter_4.to x__0, ()))
set_option smartUnfolding false in
theorem source_eq_inspectEnvelope (x__0 : @VeriSlopAST.Envelope) : source_fn_inspectEnvelope x__0 = readable_fn_inspectEnvelope x__0 := by with_unfolding_all rfl
theorem raw_eval_inspectEnvelope (x__0 : @VeriSlopAST.Envelope) :
  VSCore3.evalEntry profile rawProgram "inspectEnvelope" [adapter_4.encode x__0] =
    .ok (adapter_1.encode (readable_fn_inspectEnvelope x__0)) := by
  rw [← source_eq_inspectEnvelope x__0]
  exact VeriSlopBridgeGoal.raw_eval_inspectEnvelope x__0
def readable_fn_keepParcel (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @VeriSlopAST.Parcel) : (@List.{0} @VeriSlopAST.Envelope) := by
  with_unfolding_all exact adapter_5.inv (VeriSlopReadableSource.entry_1_run (adapter_5.to x__0, (adapter_2.to x__1, ())))
set_option smartUnfolding false in
theorem source_eq_keepParcel (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @VeriSlopAST.Parcel) : source_fn_keepParcel x__0 x__1 = readable_fn_keepParcel x__0 x__1 := by with_unfolding_all rfl
theorem raw_eval_keepParcel (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @VeriSlopAST.Parcel) :
  VSCore3.evalEntry profile rawProgram "keepParcel" [adapter_5.encode x__0, adapter_2.encode x__1] =
    .ok (adapter_5.encode (readable_fn_keepParcel x__0 x__1)) := by
  rw [← source_eq_keepParcel x__0 x__1]
  exact VeriSlopBridgeGoal.raw_eval_keepParcel x__0 x__1
def readable_fn_sameShade (x__0 : @VeriSlopAST.Shade) (x__1 : @VeriSlopAST.Shade) : @Bool := by
  with_unfolding_all exact adapter_3.inv (VeriSlopReadableSource.entry_3_run (adapter_0.to x__0, (adapter_0.to x__1, ())))
set_option smartUnfolding false in
theorem source_eq_sameShade (x__0 : @VeriSlopAST.Shade) (x__1 : @VeriSlopAST.Shade) : source_fn_sameShade x__0 x__1 = readable_fn_sameShade x__0 x__1 := by with_unfolding_all rfl
theorem raw_eval_sameShade (x__0 : @VeriSlopAST.Shade) (x__1 : @VeriSlopAST.Shade) :
  VSCore3.evalEntry profile rawProgram "sameShade" [adapter_0.encode x__0, adapter_0.encode x__1] =
    .ok (adapter_3.encode (readable_fn_sameShade x__0 x__1)) := by
  rw [← source_eq_sameShade x__0 x__1]
  exact VeriSlopBridgeGoal.raw_eval_sameShade x__0 x__1
def readable_fn_shadeTotal (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) (x__2 : @VeriSlopAST.Shade) : @Nat := by
  with_unfolding_all exact adapter_1.inv (VeriSlopReadableSource.entry_2_run (adapter_5.to x__0, (adapter_1.to x__1, (adapter_0.to x__2, ()))))
set_option smartUnfolding false in
theorem source_eq_shadeTotal (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) (x__2 : @VeriSlopAST.Shade) : source_fn_shadeTotal x__0 x__1 x__2 = readable_fn_shadeTotal x__0 x__1 x__2 := by with_unfolding_all rfl
theorem raw_eval_shadeTotal (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) (x__2 : @VeriSlopAST.Shade) :
  VSCore3.evalEntry profile rawProgram "shadeTotal" [adapter_5.encode x__0, adapter_1.encode x__1, adapter_0.encode x__2] =
    .ok (adapter_1.encode (readable_fn_shadeTotal x__0 x__1 x__2)) := by
  rw [← source_eq_shadeTotal x__0 x__1 x__2]
  exact VeriSlopBridgeGoal.raw_eval_shadeTotal x__0 x__1 x__2
def readable_fn_shiftEnvelopes (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) : (@List.{0} @VeriSlopAST.Envelope) := by
  with_unfolding_all exact adapter_5.inv (VeriSlopReadableSource.entry_0_run (adapter_5.to x__0, (adapter_1.to x__1, ())))
set_option smartUnfolding false in
theorem source_eq_shiftEnvelopes (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) : source_fn_shiftEnvelopes x__0 x__1 = readable_fn_shiftEnvelopes x__0 x__1 := by with_unfolding_all rfl
theorem raw_eval_shiftEnvelopes (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) :
  VSCore3.evalEntry profile rawProgram "shiftEnvelopes" [adapter_5.encode x__0, adapter_1.encode x__1] =
    .ok (adapter_5.encode (readable_fn_shiftEnvelopes x__0 x__1)) := by
  rw [← source_eq_shiftEnvelopes x__0 x__1]
  exact VeriSlopBridgeGoal.raw_eval_shiftEnvelopes x__0 x__1
end VeriSlopBridgeGoal.Readable
