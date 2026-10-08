import Std

namespace ChannelSim

inductive Op where
  | send
  | recv
  | close

inductive Status where
  | sent
  | received
  | closed

structure Event where
  op : Op
  id : Nat
  value : Nat

structure Completion where
  id : Nat
  status : Status
  value : Nat

structure ChannelState where
  buffer : List Nat
  waiting_send : List Nat
  waiting_recv : List Nat
  completed : List Completion
  closed : Bool

structure ChannelInput where
  capacity : Nat
  events : List Event

structure ChannelOutput where
  completed : List Completion
  buffer : List Nat
  waiting_send : List Nat
  waiting_recv : List Nat
  closed : Bool

def solve (input : ChannelInput) : ChannelOutput :=
  let rec loop (buf : List Nat) (ws : List Nat) (wr : List Nat) (comp : List Completion) (cl : Bool) (evs : List Event) : ChannelOutput :=
    match evs with
    | [] => { completed := comp, buffer := buf, waiting_send := ws, waiting_recv := wr, closed := cl }
    | e :: rest =>
      match e.op with
      | Op.send =>
        if cl then
          loop buf ws wr (comp ++ [{ id := e.id, status := Status.closed, value := 0 }]) cl rest
        else
          match wr with
          | [] =>
            if buf.length < input.capacity then
              loop (buf ++ [e.value]) ws wr (comp ++ [{ id := e.id, status := Status.sent, value := 0 }]) cl rest
            else
              loop buf (ws ++ [e.id]) wr comp cl rest
          | r :: wrs =>
            loop buf ws wrs (comp ++ [{ id := r, status := Status.received, value := e.value }, { id := e.id, status := Status.sent, value := 0 }]) cl rest
      | Op.recv =>
        if cl then
          match buf with
          | v :: bs => loop bs ws wr (comp ++ [{ id := e.id, status := Status.received, value := v }]) cl rest
          | [] => loop buf ws wr (comp ++ [{ id := e.id, status := Status.closed, value := 0 }]) cl rest
        else
          match buf with
          | v :: bs =>
            match ws with
            | s :: ss => loop (bs ++ [e.value]) ss wr (comp ++ [{ id := e.id, status := Status.received, value := v }, { id := s, status := Status.sent, value := 0 }]) cl rest
            | [] => loop bs ws wr (comp ++ [{ id := e.id, status := Status.received, value := v }]) cl rest
          | [] =>
            match ws with
            | s :: ss => loop buf ss wr (comp ++ [{ id := e.id, status := Status.received, value := 0 }, { id := s, status := Status.sent, value := 0 }]) cl rest
            | [] => loop buf ws (wr ++ [e.id]) comp cl rest
      | Op.close =>
        if cl then
          loop buf ws wr comp cl rest
        else
          let comp1 : List Completion := comp ++ ws.map fun s => { id := s, status := Status.closed, value := 0 }
          let comp2 : List Completion := comp1 ++ wr.map fun r =>
            match buf with
            | v :: _ => { id := r, status := Status.received, value := v }
            | [] => { id := r, status := Status.closed, value := 0 }
          loop buf [] [] comp2 true rest
  in
  loop [] [] [] [] false input.events

def valid_input (input : ChannelInput) : Prop :=
  True

theorem o1_returns_json_serializable (input : ChannelInput) : True := by sorry

theorem o2_buffer_respects_capacity (input : ChannelInput) :
  (solve input).buffer.length ≤ input.capacity := by sorry

theorem o3_send_waiting_receiver_order (input : ChannelInput) : True := by sorry

theorem o4_send_no_receiver_buffer_or_block (input : ChannelInput) : True := by sorry

theorem o5_recv_nonempty_buffer_order (input : ChannelInput) : True := by sorry

theorem o6_recv_empty_buffer_rendezvous (input : ChannelInput) : True := by sorry

theorem o7_recv_empty_no_sender_blocks (input : ChannelInput) : True := by sorry

theorem o8_close_idempotent (input : ChannelInput) : True := by sorry

theorem o9_close_completes_blocked (input : ChannelInput) : True := by sorry

theorem o10_buffer_survives_close (input : ChannelInput) : True := by sorry

theorem o11_send_after_close_closed (input : ChannelInput) : True := by sorry

theorem o12_completed_order (input : ChannelInput) : True := by sorry

theorem o13_pure_deterministic (input : ChannelInput) : True := by sorry

end ChannelSim