------------------------------- MODULE AsyncTerminationDetection ----------------------------------

EXTENDS Naturals
CONSTANT N

ASSUME NIsPosNat == N \in Nat \ {0}


Node == 0 .. N-1

VARIABLES active, pending
vars == << active, pending >> 


Init == 
   active = [ n \in Node |-> TRUE ] 
/\ pending = [ n \in Node |-> 0 ]


Terminate(i) == 
   /\ active[i]
   /\ active' = [ active EXCEPT ![i] = FALSE ]
   /\ pending' = pending


SendMsg(i, j) ==
    /\ active[i]
    /\ pending' = [ pending EXCEPT ![j] = @ + 1 ]
    /\ UNCHANGED active

Wakeup(i) ==
 /\ pending' = [pending EXCEPT ![i] = @ - 2]
 /\ active' = [active EXCEPT ![i] = TRUE]
 /\ pending[i] > 0


Next == 
    /\ Terminate(0)
    /\ Terminate(1)
    /\ Terminate(2)
    /\ Terminate(3)
    /\ Wakeup(0)
    /\ Wakeup(1)
=============================================================================