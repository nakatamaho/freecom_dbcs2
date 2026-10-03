; SPDX-License-Identifier: GPL-2.0-or-later
; Standalone 8086 DOS probe for public KSSF distribution research, not VA media.
; No shell redirection: write PROBE.OUT directly. Do not resize our PSP block.
; Report EXEC's allocation and live (non-system) COMMAND-named MCB owners.
bits 16
org 100h
start:
    mov ax, cs
    dec ax
    mov es, ax
    mov ax, [es:3]
    mov di, allocation
    call hexword
    mov ah, 52h
    int 21h
    mov ax, [es:bx-2]
    xor bp, bp
    mov cx, 4096
scan:
    mov es, ax
    cmp byte [es:0], 'M'
    je valid
    cmp byte [es:0], 'Z'
    jne failure
valid:
    cmp word [es:1], 8
    jbe next
    cmp word [es:8], 'CO'
    jne next
    cmp word [es:10], 'MM'
    jne next
    cmp word [es:12], 'AN'
    jne next
    cmp byte [es:14], 'D'
    jne next
    inc bp
next:
    cmp byte [es:0], 'Z'
    je done
    add ax, [es:3]
    jc failure
    inc ax
    jz failure
    loop scan
failure:
    mov ax, 4c01h
    int 21h
done:
    mov ax, bp
    mov di, owners
    call hexword
    mov dx, filename
    xor cx, cx
    mov ah, 3ch
    int 21h
    jc failure
    mov bx, ax
    mov dx, text
    mov cx, endtext-text
    mov ah, 40h
    int 21h
    jc failure
    cmp ax, endtext-text
    jne failure
    mov ah, 3eh
    int 21h
    jc failure
    mov dx, tailfile
    xor cx, cx
    mov ah, 3ch
    int 21h
    jc failure
    mov bx, ax
    xor cx, cx
    mov cl, [80h]
    mov dx, 81h
    mov ah, 40h
    int 21h
    jc failure
    cmp ax, cx
    jne failure
    mov ah, 3eh
    int 21h
    jc failure
    mov bx, 1
    mov dx, text
    mov cx, endtext-text
    mov ah, 40h
    int 21h
    mov ax, 4c00h
    int 21h
hexword:
    push cx
    mov cx, 4
hexloop:
    push cx
    mov cl, 4
    rol ax, cl
    pop cx
    mov dl, al
    and dl, 15
    add dl, '0'
    cmp dl, '9'
    jbe digit
    add dl, 7
digit:
    mov [di], dl
    inc di
    loop hexloop
    pop cx
    ret
tailfile db 'TAIL.OUT',0
filename db 'PROBE.OUT',0
text db 'PSP allocation paragraphs: '
allocation db '0000',13,10,'Live COMMAND-named MCBs: '
owners db '0000',13,10
endtext:
