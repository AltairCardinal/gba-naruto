.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global campaign_native_load
.thumb_func
campaign_native_load:
    push {r4,r5,r6,r7,lr}
    adds r1, r0, #0
    lsls r1, r1, #24
    lsrs r1, r1, #24
    ldr r3, =0x080688c1
    bx r3
.global campaign_native_suspend_load
.thumb_func
campaign_native_suspend_load:
    push {r4,r5,r6,r7,lr}
    movs r0, #1
    movs r1, #3
    ldr r3, =0x08068685
    bl campaign_storage_call
    ldr r3, =0x08068afb
    bx r3
.thumb_func
campaign_storage_call:
    bx r3
.ltorg
.global campaign_native_storage_io
.thumb_func
campaign_native_storage_io:
    push {r4,r5,r6,r7,lr}
    mov r7, sb
    mov r6, r8
    push {r6,r7}
    ldr r3, =0x0806868d
    bx r3
.ltorg
.global campaign_background
.thumb_func
campaign_background:
    push {r0,r1,r2,lr}
    bl campaign_prepare
    pop {r0,r1,r2,r3}
    cmp r4, #50
    blo 1f
    cmp r4, #56
    blo 2f
1:  ldr r1, =CAMPAIGN_MAPS
    lsls r0, r4, #5
    adds r0, r0, r1
    ldrb r0, [r0, #28]
    b 3f
2:  movs r0, r4
    subs r0, #41
3:  ldr r3, =0x0808f515
    bx r3

.global campaign_event_gate
.thumb_func
campaign_event_gate:
    push {lr}
    bl campaign_free_check
    pop {r1}
    cmp r0, #0
    beq 1f
    ldr r3, =0x0808a549
    bx r3
1:  ldr r3, =0x0808a55d
    bx r3

.global campaign_event_table_gate
.thumb_func
campaign_event_table_gate:
    push {lr}
    bl campaign_free_check
    pop {r1}
    cmp r0, #0
    beq 1f
    ldr r3, =0x0808a5e9
    bx r3
1:  ldr r1, =CAMPAIGN_EVENTS
    ldr r3, =0x0808a5d1
    bx r3

.thumb_func
campaign_free_check:
    ldr r0, =0x02026805
    ldrb r0, [r0]
    cmp r0, #56
    blo 1f
    cmp r0, #104
    bhs 1f
    movs r0, #0
    bx lr
1:  ldr r3, =0x08097131
    bx r3
.ltorg

.global campaign_original_new_game
.thumb_func
campaign_original_new_game:
    push {r0,r1,r2,lr}
    bl campaign_prepare
    pop {r0,r1,r2,r3}
    mov lr, r3
    ldr r3, =OLD_NEW_GAME
    bx r3

.global campaign_completed
.thumb_func
campaign_completed:
    ldr r0, =0x020311ea
    ldrb r0, [r0]
    cmp r0, #56
    blo 1f
    cmp r0, #104
    bhs 1f
    movs r0, #1
    bx lr
1:  movs r0, #255
    ldr r3, =0x080970a1
    bx r3

.global campaign_native_battle_init
.thumb_func
campaign_native_battle_init:
    push {r4,r5,r6,r7,lr}
    sub sp, #12
    ldr r3, =0x0806a99d
    bl 1f
    ldr r3, =0x0807518d
    bx r3
1:  bx r3
.ltorg

.global campaign_native_stats
.thumb_func
campaign_native_stats:
    push {r4,r5,r6,r7,lr}
    mov r7, sl
    mov r6, sb
    mov r5, r8
    ldr r3, =0x0806d96d
    bx r3

.global campaign_scene_start
.thumb_func
campaign_scene_start:
    push {r0,r1,r2,lr}
    bl campaign_entry
    pop {r0,r1,r2,r3}
    ldr r0, =0x020311ea
    ldrb r4, [r0]
    movs r0, r4
    ldr r3, =0x0808f545
    bl campaign_scene_call
    ldrb r0, [r5, #0x16]
    ldr r3, =0x0808f67d
    bx r3
.thumb_func
campaign_scene_call:
    bx r3

/* Extend only the rule dispatch; the native success/failure ordering remains. */
.global campaign_arrival_rule
.thumb_func
campaign_arrival_rule:
    ldrb r0, [r5]
    cmp r0, #10
    bne 1f
    push {r0,r1,r2,r3,r4,lr}
    mov r4, ip
    movs r0, r5
    bl campaign_arrived
    mov ip, r4
    cmp r0, #0
    pop {r0,r1,r2,r3,r4}
    add sp, #4
    beq 2f
    ldr r3, =0x08077b29
    bx r3
1:  subs r0, #1
    cmp r0, #8
    bhi 2f
    ldr r3, =0x08077861
    bx r3
2:  ldr r3, =0x08077b3b
    bx r3
.ltorg

/* Prevent damage before the native HP subtraction and knockout decision. */
.global campaign_damage_gate
.thumb_func
campaign_damage_gate:
    push {r0,r1,r2,r3,r4,lr}
    mov r4, ip
    mov r0, r8
    ldr r1, [sp, #44]
    bl campaign_guard_damage
    str r0, [sp, #44]
    mov ip, r4
    pop {r0,r1,r2,r3,r4}
    add sp, #4
    mov r1, r8
    ldrh r0, [r1, #12]
    ldr r2, [sp, #20]
    cmp r0, r2
    ldr r3, =0x08076b79
    bx r3
.ltorg

.global campaign_native_remove
.thumb_func
campaign_native_remove:
    push {r4,r5,r6,r7,lr}
    mov r7, sl
    mov r6, r9
    mov r5, r8
    ldr r3, =0x0806b1b1
    bx r3
.ltorg
