; SPDX-License-Identifier: GPL-2.0-or-later
; Disposable DOS guest only: retain memory until reboot for the OOM test.
; Leave no individual free block larger than 16 KiB. No hooks or disk writes.
bits 16
org 100h
    mov sp, 400h
    mov bx, 40h
    mov ah, 4ah
    int 21h
    jc fail
    mov bp, 128
again:
    mov bx, 0ffffh
    mov ah, 48h
    int 21h
    jnc fail
    cmp ax, 8
    jne fail
    cmp bx, 400h
    jbe resident
    sub bx, 400h
    mov ah, 48h
    int 21h
    jc fail
    dec bp
    jnz again
fail:
    mov ax, 4c01h
    int 21h
resident:
    mov dx, 40h
    mov ax, 3100h
    int 21h
